# CivitaiFlow Lifecycle Manager

CivitaiFlow 22.7 adds a reliability and model-lifecycle layer on top of Library Intelligence (22.5) and the Model Update Center (22.6).

The objective is to make acquisition behave more like a package manager and less like a one-shot downloader:

```text
Discover on Civitai
      ↓
Send to Forge
      ↓
Resolve exact version
      ↓
Check local inventory + disk safety
      ↓
Download / resume
      ↓
Verify SHA-256
      ↓
Install + refresh Forge
      ↓
Record lifecycle history
      ↓
Track future updates with pin / ignore policies
```

## 1. Persistent download queue

22.7 persists transfer state in:

```text
<data-dir>/civitai-flow/download-queue.json
```

The queue records the exact Civitai model/version target, destination path, temporary file path, transferred bytes, expected size, progress and terminal state.

Important queue states:

```text
resolving
queued
downloading
verifying
complete
interrupted
error
```

When Forge starts, transfers that were active during shutdown are converted to `interrupted` instead of being treated as successful or silently forgotten.

## 2. Resume support

When a `.part` file already exists, CivitaiFlow attempts to continue the transfer with an HTTP Range request:

```http
Range: bytes=<existing_size>-
```

If Civitai/CDN responds with `206 Partial Content`, CivitaiFlow appends to the existing `.part` file.

If the server ignores the Range request and returns `200`, CivitaiFlow safely restarts that transfer from byte zero rather than appending incompatible content.

If Forge was closed mid-transfer and **Resume interrupted CivitaiFlow downloads after Forge starts** is enabled, interrupted transfers are re-queued after Library Intelligence becomes ready.

The Update Center also exposes a manual **Resume N** action for resumable/error queue items.

### Integrity is still authoritative

Resume does not weaken the 22.5 integrity model.

A resumed file still goes through:

```text
.part complete
    ↓
SHA-256 calculation
    ↓
compare with Civitai SHA-256 when available
    ↓
atomic rename only after verification
```

A resumed transfer with the wrong final hash is rejected.

## 3. Disk-space guard

Large checkpoint updates can consume tens of gigabytes, especially when the safe update policy keeps older versions.

22.7 checks free space before a transfer and preserves a configurable disk reserve.

Setting:

```text
Minimum free disk space to keep after a CivitaiFlow download (GB)
```

Default:

```text
5 GB
```

The Update Center now shows estimated pending download size and current free space when the API can determine both.

Example:

```text
Model lifecycle · 9 updates available
Notify only · checked 4m ago · 31.6 GB pending · 284.2 GB free
```

A model that would violate the configured reserve is marked **Low disk** and is not queued automatically.

`Update all` keeps the same protection: models without sufficient disk headroom are skipped instead of forcing the volume to zero free space.

## 4. Per-model pinning

A Stable Diffusion model is not equivalent to a conventional application package. A newer LoRA/checkpoint can change trigger words, recommended weights, base-model assumptions or visual behavior.

22.7 therefore adds **Pin**.

A pinned model can still be updated manually, but scheduled auto-update policy will not automatically acquire the newer release.

The lifecycle policy is stored in:

```text
<data-dir>/civitai-flow/lifecycle-state.json
```

A policy record is associated with the Civitai model family (`modelId`) and can preserve the pinned local `modelVersionId` for context.

Example:

```text
Juggernaut XL
local v9 → v11
PINNED

[ Notes ] [ Unpin ] [ Ignore ] [ Civitai ↗ ] [ Update ]
```

This lets the user intentionally remain on a known-good version while still seeing that a newer version exists.

## 5. Ignore one release

**Ignore** is intentionally different from **Pin**.

Pin means:

> Do not automatically move this model family forward.

Ignore means:

> I do not want this specific remote version.

If version `v11` is ignored and the creator later publishes `v12`, a future scan can surface `v12` again.

This avoids the common update-manager problem where dismissing one bad release hides all future releases forever.

## 6. Release notes in the Update Center

22.7 carries the selected Civitai version description into the update record when the API returns one.

Each update row now exposes **Notes** so the user can review creator-provided version context before updating.

The row also includes:

- local version ID(s);
- latest Civitai version name/ID;
- model type;
- base model;
- approximate remote file size;
- pin state;
- disk-safety state;
- current queue/download status;
- direct **Civitai ↗** link.

Civitai remains the authoritative visual/detail surface; the local notes view is a convenience for update decisions.

## 7. Forge auto-refresh after install

A successful download should become usable immediately.

After an asset is verified, installed and registered in the local index, CivitaiFlow performs a best-effort Forge inventory refresh:

| Asset type | Refresh path |
| --- | --- |
| LoRA | Forge `networks.list_available_networks()` |
| Checkpoint | `modules.sd_models.list_models()` |
| VAE | `modules.sd_vae.refresh_vae_list()` |
| Textual Inversion | Forge embedding database forced reload |

This behavior is controlled by:

```text
Refresh Forge model inventories after CivitaiFlow installs an asset
```

A refresh failure does not invalidate an otherwise verified model install. The result is recorded in lifecycle history so the transfer does not become destructive simply because Forge's runtime inventory refresh changed between versions.

## 8. Lifecycle history

Install/update/error/resume/policy events are appended to:

```text
<data-dir>/civitai-flow/history.jsonl
```

History records can include:

- event timestamp;
- model ID;
- model version ID;
- model name/type;
- local path;
- SHA-256;
- previously installed version IDs;
- Forge refresh result;
- interrupted byte count;
- policy action;
- error message.

The history is append-only from CivitaiFlow's perspective. It is intended to become the foundation for a richer Update History / rollback UI without coupling that future UI to transient in-memory state.

## 9. Local API additions

22.7 adds loopback-only lifecycle endpoints:

```text
GET  /civitaiflow/api/lifecycle
GET  /civitaiflow/api/history
POST /civitaiflow/api/policy
POST /civitaiflow/api/queue/resume
POST /civitaiflow/api/queue/forget-completed
```

They use the same local-only boundary as Library Intelligence and the Update Center. Non-loopback clients are rejected by the shared CivitaiFlow API guard.

The Browser Bridge still never receives the Civitai API key.

## 10. Update Center UX in 22.7

The former **Model updates** widget is now presented as **Model lifecycle** because it combines update discovery with queue/disk/policy state.

Example:

```text
● Model lifecycle · 14 updates available
  Notify only · checked 2h ago · 42.8 GB pending · 301.2 GB free · 1 resumable

[ Review ] [ Scan ] [ Resume 1 ] [ Update all ]
```

Review rows can expose:

```text
CHECKPOINT  local 118311 → v7 · SDXL 1.0 · 6.4 GB
Realistic Example XL                         PINNED

[ Notes ] [ Unpin ] [ Ignore ] [ Civitai ↗ ] [ Update ]
```

`Update` remains an explicit manual action even for pinned models. Pin blocks automatic policy, not user intent.

## 11. Safety decisions

22.7 deliberately keeps these defaults:

- **KEEP BOTH** remains the effective update behavior.
- Old model files are not automatically deleted.
- SHA-256 remains the strongest duplicate/integrity signal.
- A `.part` file is never promoted before verification.
- Auto-update respects pin state.
- Ignored releases remain ignored until a newer release appears or the policy is cleared.
- Disk reserve is checked before queueing large downloads.
- Resume is best-effort and gracefully restarts when the remote server does not support Range requests.

## 12. Runtime data files

CivitaiFlow now uses these local state files:

```text
<data-dir>/civitai-flow/
├── library-index.json     # SHA/model/version inventory
├── update-cache.json      # latest known Civitai update scan
├── lifecycle-state.json   # pin/ignore policies
├── download-queue.json    # persistent transfer state
└── history.jsonl          # lifecycle audit trail
```

These files contain model/library state. They do not contain the Civitai API key.

## 13. Remaining lifecycle work

The next lifecycle improvements should be built on this state instead of adding another parallel database:

1. **Archive old** and **Replace old** as explicit opt-in update policies.
2. Full **History / rollback** UI with version activation helpers.
3. Pause/cancel/reorder controls for the persistent queue.
4. Better retry classification for authentication errors vs transient CDN/network failures.
5. Storage templates and migrations when the user changes organization rules.
6. Library Health: exact duplicates, orphan sidecars, missing previews, stale entries and repair actions.
7. File-variant preferences such as safetensors / FP16 / pruned.
8. Browser Bridge configurable Forge endpoint + local bridge token.
9. Secure Windows credential storage.
10. Civitai OAuth + PKCE once CivitaiFlow has its own registered OAuth client.
11. Modularize the compatibility-layer scripts into a stable internal package before a future major version.

The product direction remains unchanged:

> **Use Civitai as the visual repository, let CivitaiFlow manage acquisition and lifecycle, and let Forge remain the runtime.**
