# CivitaiFlow

> **See it on Civitai. Send it to Forge. Keep the local library clean.**

CivitaiFlow is a visual Civitai-to-Forge acquisition and model-lifecycle layer for **Stable Diffusion WebUI Forge**.

It keeps the real Civitai discovery experience — previews, creators, versions, examples and model pages — while automating everything that becomes repetitive after you decide you want an asset.

```text
Browse visually on Civitai
        ↓
Send to Forge / copy model link
        ↓
Resolve exact model + version
        ↓
Check local SHA-256 inventory
        ↓
Already installed? ── yes → stop, no duplicate
        │
        no
        ↓
Disk guard → download/resume → SHA verify
        ↓
Route → metadata → register → refresh Forge
        ↓
Lifecycle history
        ↓
Future release?
        ↓
Update Center → Pin / Ignore / Update / Auto-update
```

## Product principles

### 1. Visual discovery stays visual

Civitai itself remains the discovery surface. CivitaiFlow does not replace it with a reduced API gallery.

Use:

- **Embedded Civitai** inside Forge when browser/Civitai framing policy allows it.
- **Companion Window** as the normal top-level Civitai experience for reliable login or when iframe behavior breaks.

### 2. Acquisition should be one action

Original workflow:

```text
See model → right-click → Copy link → Sniper → Auto-DL
```

With the optional **CivitaiFlow Browser Bridge**:

```text
See model → Send to Forge
```

### 3. The local library should know what it owns

CivitaiFlow indexes assets using:

- Civitai model ID;
- Civitai `modelVersionId`;
- SHA-256;
- local path;
- model/asset type.

That lets CivitaiFlow distinguish:

```text
Send to Forge
Installed
Update available
Downloading 64%
Verifying
Pinned
Low disk
```

### 4. Updates should be safe

A newer LoRA/checkpoint can change trigger words, recommended weight, base model assumptions or visual behavior.

CivitaiFlow therefore treats auto-update as **automatic acquisition of a newer version**, not automatic destruction of the old one.

**KEEP BOTH** remains the safe default.

---

# 22.7 — Reliability & Lifecycle

22.7 turns the 22.5/22.6 acquisition engine into a more durable model lifecycle manager.

## Persistent queue + resume

Transfer state is persisted in:

```text
<data-dir>/civitai-flow/download-queue.json
```

Interrupted transfers keep their `.part` file and can resume with HTTP Range requests when the Civitai CDN supports them.

```text
Downloading 63%
     ↓
Forge closes / PC restarts
     ↓
CivitaiFlow sees interrupted queue item
     ↓
Range: bytes=<existing_size>-
     ↓
Resume
     ↓
SHA-256 verify before install
```

If the server does not support resume, CivitaiFlow safely restarts that transfer from byte zero rather than appending incompatible bytes.

The lifecycle panel exposes **Resume N** when resumable/error queue items exist.

## Disk-space protection

Before a model is queued, CivitaiFlow estimates required space and preserves a configurable disk reserve.

Default reserve:

```text
5 GB
```

The lifecycle UI can show:

```text
14 updates · 42.8 GB pending · 301.2 GB free
```

A model that would violate the reserve is marked **Low disk** and is not auto-queued.

## Pin a model

A pinned model can still be updated manually, but scheduled auto-update will leave it alone.

```text
Juggernaut XL
local v9 → v11
PINNED

[ Notes ] [ Unpin ] [ Ignore ] [ Civitai ↗ ] [ Update ]
```

## Ignore one release

**Ignore** suppresses only the currently offered Civitai version.

If you ignore `v11` and the creator later publishes `v12`, the next scan can show `v12` again.

## Release notes before update

Update rows now carry version description/release context returned by the Civitai API and expose a compact **Notes** action before downloading.

Rows can show:

- local version(s);
- latest Civitai version;
- type;
- base model;
- approximate download size;
- pin state;
- disk state;
- current transfer state;
- direct Civitai link.

## Forge auto-refresh

After a verified install CivitaiFlow performs a best-effort Forge inventory refresh:

| Asset | Refresh |
| --- | --- |
| LoRA | Forge network inventory |
| Checkpoint | checkpoint model list |
| VAE | VAE list |
| Textual Inversion | embedding database |

A refresh failure does not invalidate an otherwise good model download; the result is recorded in lifecycle history.

## Lifecycle history

Install/update/resume/error/policy events are appended to:

```text
<data-dir>/civitai-flow/history.jsonl
```

This becomes the foundation for a future full rollback/history UI.

See [Lifecycle Manager](docs/LIFECYCLE.md).

---

# 22.6 — Model Update Center

CivitaiFlow groups locally indexed files by Civitai model family, checks the latest downloadable version and compares the remote `modelVersionId`/SHA-256 with the local library.

```text
Local model family
      ↓
Civitai latest version
      ↓
latest version/hash already local?
      │
      ├─ yes → CURRENT
      └─ no  → UPDATE AVAILABLE
```

Available update modes under **Forge → Settings → CivitaiFlow Manager**:

- **Disabled**
- **Notify only** — default
- **Auto-download LoRAs (keep old)**
- **Auto-download LoRAs + checkpoints (keep old)**

See [Model Updates](docs/UPDATES.md).

---

# 22.5 — Library Intelligence

CivitaiFlow maintains an incremental local inventory in:

```text
<data-dir>/civitai-flow/library-index.json
```

The first scan hashes supported model files. Later scans reuse cached hashes for unchanged files.

For older/manual assets without CivitaiFlow metadata, SHA-256 can be resolved through Civitai's public by-hash API so many pre-existing models can still be connected back to their Civitai model/version IDs.

## Duplicate prevention

Before a smart transfer starts, CivitaiFlow checks:

1. exact remote SHA-256;
2. exact Civitai `modelVersionId` when known;
3. installed model family for update awareness.

An exact file is not downloaded twice even when its filename or folder changed.

## Type-aware routing

| Civitai type | Forge location |
| --- | --- |
| LoRA | `models/Lora` |
| Checkpoint | `models/Stable-diffusion` |
| VAE | `models/VAE` |
| Textual Inversion | `<data-dir>/embeddings` |

Unsupported types fail explicitly instead of silently landing in the LoRA directory.

## Integrity

Smart transfers use:

```text
*.part
  ↓
stream / resume
  ↓
SHA-256 verification
  ↓
atomic rename
```

See [Library Intelligence](docs/LIBRARY-INTELLIGENCE.md).

---

# Browser Bridge

The optional Manifest V3 Browser Bridge lives in [`browser-extension/`](browser-extension/).

It enhances the **real Civitai website** with one-click local-library actions instead of recreating the site.

```text
Civitai card
    ↓
Send to Forge
    ↓
Browser Bridge
    ↓
127.0.0.1:7860/civitaiflow/api/*
    ↓
CivitaiFlow smart acquisition
```

When the local bridge is unavailable, it falls back to copying the canonical Civitai URL so the original Windows Sniper workflow still works.

The Browser Bridge never receives the Civitai API key.

## Install in Edge / Chrome

1. Update CivitaiFlow and restart Forge.
2. Open `edge://extensions` or `chrome://extensions`.
3. Enable **Developer mode**.
4. Choose **Load unpacked** or **Reload**.
5. Select `CivitaiFlow/browser-extension`.
6. Reload Civitai.

See [Browser Bridge documentation](browser-extension/README.md).

---

# Authentication

CivitaiFlow interacts with two separate authentication systems.

## Website session

The Civitai website uses browser cookies and its normal Civitai/Google login flow.

Google OAuth can reject authentication inside embedded user-agents/iframes and browser privacy rules can isolate third-party cookies.

Use **Open Companion Window** when login inside the iframe fails.

## API credential

CivitaiFlow's Python backend uses the configured Civitai API key for authenticated metadata and gated downloads:

```http
Authorization: Bearer <CIVITAI_API_KEY>
```

The API key does not create a Civitai website cookie and cannot log the iframe into the website.

See [Authentication](docs/AUTHENTICATION.md).

---

# Runtime state

CivitaiFlow keeps model-management state under Forge's data directory:

```text
<data-dir>/civitai-flow/
├── library-index.json
├── update-cache.json
├── lifecycle-state.json
├── download-queue.json
└── history.jsonl
```

These model-management files do **not** contain the Civitai API key.

---

# Core features

- Real Civitai website as the visual discovery experience.
- Embedded mode plus Companion Window fallback.
- Optional one-click Browser Bridge.
- Live Installed / Update / Downloading states while browsing.
- Windows clipboard Sniper fallback.
- Civitai API-key verification and Bearer authentication.
- Exact `modelVersionId` resolution.
- Incremental SHA-256 local inventory.
- Cross-folder duplicate prevention.
- LoRA/checkpoint/VAE/Textual-Inversion routing.
- Concurrent background transfers.
- Persistent queue state.
- Best-effort HTTP Range resume.
- `.part` safety + SHA-256 verification.
- Disk reserve guard.
- Collision-safe multi-version installs.
- Preview + Forge metadata generation.
- Forge model inventory refresh after install.
- Scheduled update discovery.
- Manual per-model / Update all.
- Safe optional auto-update while keeping older versions.
- Per-model Pin / Unpin.
- Ignore a specific remote release.
- Release notes inside update review.
- Lifecycle history.

---

# Quick start

1. Install through **Forge → Extensions → Install from URL**:

   `https://github.com/roninhub121/CivitaiFlow`

2. Apply changes and fully restart Forge.
3. Open **CivitaiFlow**.
4. Configure a Civitai API key when authenticated/gated access is required.
5. Let **Library Intelligence** finish the initial index.
6. Optionally load/reload the Browser Bridge.
7. Browse Civitai visually and use **Send to Forge**.
8. Use **Model lifecycle** to scan/review updates, pin known-good versions, ignore bad releases and resume interrupted transfers.

---

# Local API

Loopback-only endpoints include:

```text
GET  /civitaiflow/api/health
GET  /civitaiflow/api/status
POST /civitaiflow/api/capture
GET  /civitaiflow/api/library
POST /civitaiflow/api/reindex

GET  /civitaiflow/api/updates
POST /civitaiflow/api/updates/scan
POST /civitaiflow/api/updates/apply
POST /civitaiflow/api/updates/apply-all

GET  /civitaiflow/api/lifecycle
GET  /civitaiflow/api/history
POST /civitaiflow/api/policy
POST /civitaiflow/api/queue/resume
POST /civitaiflow/api/queue/forget-completed
```

These endpoints reject non-loopback clients through the shared local API guard.

---

# Current limitations

- Embedded Civitai remains dependent on Civitai/browser framing policy.
- Browser Bridge currently assumes local Forge on the default port `7860`.
- Initial SHA-256 indexing can be disk-intensive for very large libraries.
- Civitai card placement still depends on DOM heuristics.
- Sniper capture remains Windows/PowerShell-specific.
- Resume depends on remote HTTP Range support; unsupported servers restart the individual transfer safely.
- KEEP BOTH is still the only implemented update storage policy; Archive/Replace are future explicit opt-ins.
- History is persisted but does not yet have a full rollback UI.
- Queue pause/cancel/reorder controls are not implemented yet.
- API keys still use Forge configuration rather than DPAPI/Credential Manager.
- The Python core is still layered around the original monolithic script and should be modularized before a future major release.

---

# Recommended roadmap

1. **Library Health** — exact duplicates, missing previews, orphan sidecars, stale entries and repair actions.
2. **History + rollback UI** — inspect prior installs and activate/archive older versions cleanly.
3. **Queue controls** — pause, cancel, reorder and retry classification.
4. **Archive old / Replace old** — explicit opt-in alternatives to KEEP BOTH.
5. **File-variant preferences** — safetensors, FP16, pruned, primary-file rules.
6. **User-defined storage rules** — type/base model/creator/custom templates.
7. **Browser Bridge configuration** — Forge URL/port + local bridge token.
8. **Secure credential storage** — Windows DPAPI/Credential Manager.
9. **Official Civitai OAuth + PKCE** — after registering CivitaiFlow as its own OAuth client.
10. **Modular Python core** — split client, resolver, library, queue, lifecycle, storage and metadata into a stable internal package.

---

# Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Authentication](docs/AUTHENTICATION.md)
- [Library Intelligence](docs/LIBRARY-INTELLIGENCE.md)
- [Model Updates](docs/UPDATES.md)
- [Lifecycle Manager](docs/LIFECYCLE.md)
- [Browser Bridge](browser-extension/README.md)
- [Testing](docs/TESTING.md)
- [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).

## Credits

Developed and maintained by **Ronin**.

Built for the Stable Diffusion WebUI Forge workflow.
