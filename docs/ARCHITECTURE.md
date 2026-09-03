# CivitaiFlow Architecture

This document describes the product objective, the 22.5 runtime architecture, browser/iframe constraints, local-library intelligence, and the next engineering priorities.

## 1. Product objective

CivitaiFlow exists to minimize the work between **visually discovering a Civitai asset** and **having the correct, non-duplicate asset ready in Stable Diffusion WebUI Forge**.

The product loop is:

```text
DISCOVER → SELECT → RESOLVE → DEDUP → AUTHENTICATE → DOWNLOAD → VERIFY → ORGANIZE → USE
```

The visual Civitai surface matters because model acquisition is not just an API query: previews, versions, examples, creator context and model pages are part of the user's decision.

The local library matters because repeatedly downloading the same bytes under different names is wasteful and makes large Forge repositories increasingly difficult to manage.

## 2. Discovery surfaces

CivitaiFlow intentionally supports more than one Civitai website surface.

### Embedded Civitai

The Forge tab keeps a large Civitai iframe when browser/Civitai policy permits it.

This is the most integrated experience, but it is a best-effort external dependency. Civitai controls framing headers/CSP and the browser controls third-party cookie behavior.

### Companion Window

`javascript/civitai_flow.js` opens Civitai as a normal top-level window in the same browser profile.

Use it for:

- Google/Civitai login;
- account/API-key management;
- browsing when the iframe is blocked;
- first-party Civitai cookies;
- the same Browser Bridge one-click controls.

### Browser Bridge

`browser-extension/` is an optional Manifest V3 extension that runs on `https://civitai.com/*` with `all_frames: true`.

It adds controls directly to the real Civitai page because Forge cannot modify a cross-origin iframe DOM from the parent page.

In 22.5 the Browser Bridge is no longer just a clipboard helper. It can query the local Forge inventory and display:

```text
Send to Forge
Installed
Update available
Queued
Downloading 64%
Verifying
Indexing library
```

## 3. Authentication model

Website authentication and acquisition authentication remain separate systems.

### Website session

The Civitai website uses browser cookies and Civitai/Google login.

Google OAuth can reject embedded authorization and a successful top-level login does not guarantee that third-party iframe cookie state will be reusable.

### API credential

The Forge backend uses a Civitai Bearer credential for authenticated metadata/download operations:

```http
Authorization: Bearer <CIVITAI_API_KEY>
```

The Browser Bridge never receives this credential.

OAuth + PKCE remains the preferred future UX once CivitaiFlow has its own registered Civitai OAuth client.

## 4. 22.5 runtime architecture

```text
Civitai website
  ├─ embedded iframe
  └─ Companion Window
          │
          ├─ Browser Bridge button ───────────────┐
          │                                      │
          └─ manual copy / Sniper fallback       │
                                                 ▼
                                   Local Forge bridge API
                                                 │
                               ┌─────────────────┴─────────────────┐
                               ▼                                   ▼
                         Target resolver                     Library index
                               │                                   │
                         exact version                       SHA-256 / IDs
                               │                                   │
                               └──────────────┬────────────────────┘
                                              ▼
                                      duplicate decision
                                              │
                         ┌────────────────────┴────────────────────┐
                         ▼                                         ▼
                      installed                                 download
                                                                    │
                                                              *.part file
                                                                    │
                                                               SHA-256 verify
                                                                    │
                                                               storage router
                                                                    │
                                                            sidecars + preview
                                                                    │
                                                             register in index
```

## 5. Python composition strategy

The historical UI remains in `scripts/ronin_ui.py`.

22.5 adds `scripts/zz_civitaiflow_library.py` as a compatibility/upgrade layer loaded after the original script. Forge loads extension scripts in order, so this module can locate the already-loaded `ronin_ui.py` module through Forge's `script_loading.loaded_scripts` registry.

The smart layer then replaces the legacy URL parser/download entry point used by the timer at runtime:

- version-aware target parsing;
- smart queueing;
- library duplicate checks;
- model-type routing;
- SHA-256 verification.

This approach avoids a risky full rewrite of the established Gradio UI while moving acquisition behavior toward the target architecture.

Long term, the compatibility layer should be folded into explicit modules rather than remaining a monkey-patch boundary.

## 6. Local Library Intelligence

The index is stored outside the repository in Forge's data directory:

```text
<data-dir>/civitai-flow/library-index.json
```

It records:

- absolute local path;
- local model kind;
- file size;
- nanosecond modification time;
- SHA-256;
- Civitai model ID when known;
- Civitai model version ID when known.

### Incremental hashing

Every Forge start launches a background scan.

Unchanged files reuse their cached hash. New or modified files are hashed. Deleted paths are removed from the new snapshot.

The first scan is intentionally conservative: smart downloads are held until the library inventory is ready. This protects the duplicate-prevention invariant during startup.

### Identifying manually managed models

CivitaiFlow first reads local JSON sidecars. For files without model/version metadata it batches SHA-256 values through Civitai's by-hash endpoint (up to 100 hashes per request) and annotates recognized files.

This allows the library index to understand many files that existed before CivitaiFlow 22.5 or were renamed/moved manually.

See [Library Intelligence](LIBRARY-INTELLIGENCE.md).

## 7. Duplicate decision hierarchy

The smart resolver obtains the remote target file and SHA-256 when available.

The duplicate check prefers:

1. exact SHA-256 match;
2. exact `modelVersionId` match from indexed metadata;
3. model-family presence for `Update available` state.

Filename equality alone is not treated as proof that two model files are identical.

If the destination filename already exists with different bytes, the incoming file receives a version suffix rather than overwriting the existing model blindly.

## 8. Version-aware resolution

A copied/sent URL can contain:

```text
?modelVersionId=987654
```

22.5 preserves that value and selects the matching Civitai version explicitly.

If no `modelVersionId` is supplied, the current/first version returned by the model API remains the target. For an already indexed model family, the status layer can resolve that current target and report whether the local version is exact or stale.

## 9. Storage router

22.5 maps supported Civitai types to Forge locations:

```text
LORA              → models/Lora
Checkpoint        → models/Stable-diffusion
VAE               → models/VAE
TextualInversion  → <data-dir>/embeddings
```

Unsupported types fail explicitly.

LoRA still retains the legacy first-tag subfolder behavior for compatibility. Replacing remote-tag organization with user-defined rules is a future improvement.

## 10. Transfer integrity

The smart download lifecycle is:

```text
downloadUrl
   ↓
filename.ext.part
   ↓
stream + progress
   ↓
SHA-256
   ↓
compare with Civitai hash when present
   ↓
atomic os.replace()
   ↓
metadata + preview
   ↓
index registration
```

A hash mismatch removes the temporary transfer and does not promote corrupted bytes into the model repository.

## 11. Local Browser Bridge API

The smart layer registers loopback-only FastAPI routes through Forge `script_callbacks.on_app_started`:

```text
GET  /civitaiflow/api/health
GET  /civitaiflow/api/status
POST /civitaiflow/api/capture
GET  /civitaiflow/api/library
POST /civitaiflow/api/reindex
```

The server validates the request client as loopback (`127.0.0.1` / `::1`).

The Browser Bridge service worker has host permissions only for Civitai plus local HTTP origins and prefers `127.0.0.1:7860`, then `localhost:7860`.

This is intentionally local-only. A future remote-Forge mode should require an explicit endpoint plus an authentication token rather than silently trusting LAN access.

## 12. Browser Bridge fallback behavior

Preferred path:

```text
Send to Forge → local service worker bridge → Forge smart queue
```

Fallback path when Forge cannot be reached:

```text
Send to Forge → clipboard → Windows Sniper → Forge smart queue
```

The original workflow therefore remains usable if the browser-side direct bridge is unavailable.

## 13. Current risk register

### P0 — iframe availability remains external

Civitai/browser policy can still block the embedded website. Companion Window remains the supported resilience mechanism.

### P1 — first index can be expensive

Hashing a large checkpoint repository can cause sustained disk reads. This cost is paid primarily for new/changed files; later scans reuse cached hashes.

### P1 — legacy UI and smart core are still coupled

The 22.5 compatibility module deliberately patches legacy entry points rather than rewriting `ronin_ui.py` in one release.

The next architectural cleanup should extract stable interfaces for client, resolver, index, queue, storage and metadata.

### P1 — Forge inventory refresh after download

A model can be on disk before Forge's UI/network lists notice it. Automatic LoRA/checkpoint refresh should be added after successful installation.

### P2 — queue state is not persistent

Active/failed download state still lives in process memory. Restarting Forge loses the queue.

### P2 — update policy is implicit

22.5 preserves existing files and uses version-suffixed collisions, but there is no user-selectable keep/replace/archive policy yet.

### P2 — storage taxonomy is not user-defined

LoRA tag-based subfolders are retained for compatibility but Civitai's first tag is not a durable local taxonomy.

### P2 — API-key storage

The key is still stored through Forge configuration rather than a CivitaiFlow-specific secure secret store.

## 14. Target modular architecture

The next refactor should converge toward:

```text
civitai_flow/
  client.py              # REST/auth calls + response normalization
  targets.py             # URL/model/version parsing
  library.py             # persistent local inventory / hashing
  resolver.py            # remote target resolution + duplicate decision
  queue.py               # persistent jobs / retries / progress
  storage.py             # model-type + user-rule routing
  transfer.py            # streaming / integrity verification
  metadata.py            # preview and Forge sidecars
  bridge_api.py          # loopback Browser Bridge contract

auth/
  api_key.py
  oauth_pkce.py          # future

scripts/
  civitaiflow_ui.py      # Forge / Gradio composition only
```

The browser-side layers should remain separate:

```text
javascript/civitai_flow.js       # Forge Companion Window UX
javascript/library_status.js     # Forge local index status
browser-extension/               # Civitai page enhancement
```

## 15. Recommended next implementation order

1. **Forge refresh after install** for LoRA/checkpoint inventories.
2. **Persistent download queue** with safe resume metadata.
3. **Explicit update policy**: keep old / replace / archive.
4. **Library repair view** for duplicates, orphan sidecars and missing previews.
5. **User-defined storage rules** by model type/base model/creator/category.
6. **Configurable Browser Bridge endpoint** with an explicit bridge token.
7. **Secure Windows credential storage**.
8. **Register CivitaiFlow OAuth client and add PKCE**.
9. **Refactor the compatibility layer into the modular core above**.

## 16. Non-goals

CivitaiFlow should not become:

- a replacement Civitai social client;
- a cookie/credential extraction tool;
- a reverse proxy whose purpose is defeating anti-framing policy;
- an unrelated generic model manager detached from Civitai discovery.

The focus remains: **see it on Civitai, acquire it safely, keep Forge clean.**
