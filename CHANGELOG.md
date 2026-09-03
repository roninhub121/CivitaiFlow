# Changelog

All notable changes to CivitaiFlow are documented here.

## [22.7] - 2026-09-03

### Reliability & Lifecycle

- Added `scripts/zzzz_civitaiflow_lifecycle.py` as a compatibility layer on top of Library Intelligence and the Model Update Center.
- Added persistent transfer state under `<data-dir>/civitai-flow/download-queue.json`.
- Active transfers from a previous Forge session are marked `interrupted` on startup rather than silently forgotten.
- Added best-effort HTTP Range resume for existing `.part` files.
- If a remote server ignores Range and returns a normal `200`, CivitaiFlow safely restarts that individual transfer instead of appending incompatible bytes.
- Resumed transfers still require final SHA-256 verification before atomic promotion.

### Disk safety

- Added a configurable free-space reserve under **Forge → Settings → CivitaiFlow Manager**.
- Default reserve is 5 GB.
- Update records now include approximate remote file size and local free-space state when available.
- Models that would violate the configured reserve are marked **Low disk** and are skipped by automatic update acquisition.
- **Update all** now shows estimated pending download size/free space and keeps the same disk guard.

### Update policies

- Added per-model **Pin / Unpin** policy.
- Pinned models remain visible in update review but are excluded from scheduled auto-update.
- Manual **Update** still works for a pinned model because pin protects automation, not explicit user intent.
- Added **Ignore** for a specific remote `modelVersionId`.
- Ignoring one release does not permanently suppress future releases; a later Civitai version can appear on a future scan.
- Policies persist under `<data-dir>/civitai-flow/lifecycle-state.json`.

### Update review UX

- Upgraded `javascript/update_center.js` from **Model updates** to **Model lifecycle**.
- Added release-note/version-description review when supplied by Civitai.
- Added per-model **Notes**, **Pin / Unpin**, **Ignore**, **Civitai ↗**, and **Update** actions.
- Added file-size/base-model context, pinned badges, low-disk badges, pending-download totals and free-space context.
- Added **Resume N** for resumable/error queue entries.
- Updated the visible CivitaiFlow badge to `v22.7` from the lifecycle UI.

### Forge refresh

- Added best-effort automatic runtime inventory refresh after a successful verified install:
  - LoRA → Forge networks inventory;
  - Checkpoint → `sd_models.list_models()`;
  - VAE → `sd_vae.refresh_vae_list()`;
  - Textual Inversion → embedding database forced reload.
- Refresh failure does not invalidate a verified model install; the result is recorded in lifecycle history.

### Lifecycle history

- Added append-only lifecycle history under `<data-dir>/civitai-flow/history.jsonl`.
- Records install/update/resume/error/policy events with model/version IDs, paths, hashes, previous versions and Forge-refresh result when available.

### Local API

- Added loopback-only lifecycle endpoints:
  - `GET /civitaiflow/api/lifecycle`;
  - `GET /civitaiflow/api/history`;
  - `POST /civitaiflow/api/policy`;
  - `POST /civitaiflow/api/queue/resume`;
  - `POST /civitaiflow/api/queue/forget-completed`.

### Validation and documentation

- CI now compiles all Python compatibility layers, including the 22.6 updater and 22.7 lifecycle manager.
- CI now syntax-checks `javascript/update_center.js`.
- Added `docs/LIFECYCLE.md` with queue/resume semantics, disk guard, pin/ignore behavior, release notes, Forge refresh, history, local API and remaining lifecycle roadmap.
- Refreshed the main README around the full product loop: visual Civitai discovery → smart acquisition → clean local library → durable lifecycle management.

## [22.6] - 2026-09-03

### Model Update Center

- Added `scripts/zzz_civitaiflow_updates.py` on top of the 22.5 Library Intelligence layer.
- Added scheduled scans that group the indexed local library by Civitai model ID and check the newest downloadable Civitai version for each known model family.
- Update detection compares the latest remote `modelVersionId` and SHA-256 with the local index instead of relying on filenames.
- Added persisted update metadata under `<data-dir>/civitai-flow/update-cache.json`.
- Added `javascript/update_center.js` with a compact Forge **Model updates** panel, manual scan, review list, per-model update action and **Update all** action.
- The Update Center shows live queued/downloading state by reusing the Library Intelligence status layer.

### Safe auto-update

- Added four update modes in **Forge → Settings → CivitaiFlow Manager**:
  - `Disabled`;
  - `Notify only` (default);
  - `Auto-download LoRAs (keep old)`;
  - `Auto-download LoRAs + checkpoints (keep old)`.
- Added configurable update-check interval, auto-update concurrency, maximum automatic updates per scan, and startup check toggle.
- Scheduled auto-update deliberately keeps existing model versions. v22.6 never deletes or blindly replaces an older checkpoint/LoRA as part of automatic updating.
- Automatic updates are handed to the existing smart acquisition path using the exact target `modelVersionId`, so duplicate checks, storage routing, `.part` transfers, SHA-256 verification, collision-safe filenames, metadata and index registration are reused.
- Automatic update batches are capped per scan by default to avoid unexpectedly queueing a very large library all at once.

### Local API

- Added loopback-only update endpoints:
  - `GET /civitaiflow/api/updates`;
  - `POST /civitaiflow/api/updates/scan`;
  - `POST /civitaiflow/api/updates/apply`;
  - `POST /civitaiflow/api/updates/apply-all`.
- Update endpoints inherit the same local-only security boundary as Library Intelligence.

### Documentation

- Added `docs/UPDATES.md` with update semantics, scheduler behavior, safe auto-update policies, local API, Browser Bridge relationship, and the future pin/archive/rollback roadmap.

## [22.5] - 2026-09-03

### Library Intelligence

- Added `scripts/zz_civitaiflow_library.py`, a smart acquisition compatibility layer loaded after the existing Forge UI script.
- Added a persistent incremental local model index under `<data-dir>/civitai-flow/library-index.json`.
- Added SHA-256 indexing for supported Forge model repositories.
- Unchanged files reuse cached hashes; new/modified files are rehashed.
- Existing CivitaiFlow JSON sidecars are read for model/version IDs.
- Unknown local SHA-256 values can be resolved through Civitai's batch `POST /api/v1/model-versions/by-hash` endpoint.
- Smart downloads are held until the startup library index is ready so duplicate protection cannot be bypassed during index warm-up.

### Duplicate and update awareness

- Exact SHA-256 matches are treated as already installed regardless of filename or folder.
- Exact indexed `modelVersionId` matches are also treated as installed.
- A different local version from the same Civitai model family is surfaced as **Update available**.
- Destination filename collisions no longer blindly overwrite different bytes; the incoming file receives a `__v<modelVersionId>` suffix.

### Version-aware acquisition

- Civitai URLs now preserve `modelVersionId` through the smart resolver.
- A requested version is selected explicitly instead of intentionally discarding the version selector and always using the first API version.
- Missing/unavailable requested versions fail clearly.

### Model routing

- Added type-aware routing for:
  - `LORA` → `models/Lora`;
  - `Checkpoint` → `models/Stable-diffusion`;
  - `VAE` → `models/VAE`;
  - `TextualInversion` → `<data-dir>/embeddings`.
- Unsupported Civitai types fail explicitly instead of silently landing in the LoRA repository.

### Integrity

- Smart transfers download to `*.part`.
- Completed transfers are SHA-256 hashed before promotion.
- Civitai SHA-256 is enforced when available.
- Hash mismatches reject/remove the temporary transfer instead of creating a seemingly valid local model.
- New JSON sidecars include model ID, version ID, model type, source filename and SHA-256.

### Local Browser Bridge API

- Added loopback-only Forge endpoints:
  - `GET /civitaiflow/api/health`;
  - `GET /civitaiflow/api/status`;
  - `POST /civitaiflow/api/capture`;
  - `GET /civitaiflow/api/library`;
  - `POST /civitaiflow/api/reindex`.
- The API rejects non-loopback clients to avoid turning a Forge `--listen` instance into an unauthenticated LAN download surface.

### Browser Bridge 0.2

- Added `browser-extension/background.js` as a Manifest V3 service-worker bridge to local Forge.
- Added local host permissions for `127.0.0.1` and `localhost` while retaining Civitai-only page access.
- **Send to Forge** now prefers the direct local Forge API instead of clipboard transport.
- Clipboard/Sniper remains an automatic fallback when local Forge cannot be reached.
- Civitai model cards/pages now show live local state:
  - **Installed**;
  - **Update available**;
  - **Queued**;
  - **Downloading %**;
  - **Verifying**;
  - **Indexing library**.
- Installed/update/downloading states remain visible without requiring card hover.
- The Browser Bridge still never receives the user's Civitai API credential.

### Forge UI

- Added `javascript/library_status.js`.
- The Civitai connection card now receives a compact library status row with indexed counts and a **Reindex** action.
- The widget polls the local CivitaiFlow library service without exposing Civitai credentials to JavaScript.

### Documentation

- Added `docs/LIBRARY-INTELLIGENCE.md`.
- Refreshed the main README around the product statement: **See it on Civitai. Send it to Forge. Keep the local library clean.**
- Updated architecture documentation to reflect the smart resolver, persistent index, local bridge, routing and SHA-256 verification.
- Rewrote Browser Bridge documentation for direct mode, live states, permissions, loopback security and Sniper fallback.

## [22.4.2] - 2026-09-03

### Added

- Added the optional `browser-extension/` **CivitaiFlow Browser Bridge** for Chrome and Microsoft Edge.
- Added one-click **Send to Forge** controls directly on Civitai model cards.
- Added a persistent **Send to Forge** action on Civitai model detail pages.
- The Browser Bridge runs on `https://civitai.com/*` with `all_frames: true`, so it can enhance both the embedded Civitai view and the top-level Companion Window when the browser permits the page to render.
- Successful button clicks originally copied the canonical Civitai model URL to the clipboard so the existing Sniper capture + Auto Download pipeline could be reused.
- `modelVersionId` is preserved when it is already present in the source URL.
- Added lightweight SVG button states and Browser Bridge documentation.

### Architecture

- Per-card controls are implemented as an explicit browser content script rather than attempting to reach into the cross-origin Civitai iframe from Forge JavaScript.
- This avoids reverse-proxying Civitai, stripping frame/CSP protections, copying session cookies, or creating an alternate website renderer.

## [22.4.1] - 2026-09-03

### Added

- Added `javascript/civitai_flow.js` as a browser-side Companion Window enhancement.
- The existing **Open Civitai in Browser** action is upgraded client-side to **Open Companion Window ↗**.
- Companion browsing opens Civitai as a normal top-level window in the same browser running Forge.
- Closing the companion window triggers a best-effort reload of the embedded Civitai panel.
- **Get API Key ↗** opens the current Civitai Account page in the same browser profile.
- Added `docs/ARCHITECTURE.md` and `docs/AUTHENTICATION.md`.

### Documentation refresh

- Reframed CivitaiFlow around its actual product goal: discover visually on Civitai, acquire safely, and use locally in Forge.
- Documented Companion Window mode as the supported fallback when embedding or iframe authentication fails.
- Documented why an API key authenticates backend downloads but cannot create a Civitai website session.
- Documented OAuth + PKCE as the preferred future API-authentication UX once CivitaiFlow has its own registered client.

## [22.4] - 2026-09-03

### Added

- Inline **Civitai connection** card inside the main CivitaiFlow tab.
- Masked API-key input.
- **Connect API** validates a candidate key against `GET /api/v1/me` before persisting it.
- **Verify**, **Get API Key**, and **Disconnect** actions.
- Authenticated username display and masked key suffix.
- Custom CivitaiFlow SVG mark, version badge and card-based control-deck styling.

### Authentication

- Valid API keys are persisted through Forge's configuration path.
- API authentication uses `Authorization: Bearer <CIVITAI_API_KEY>`.
- The API credential authenticates CivitaiFlow API/download requests; it does not replace the embedded website session.

## [22.3] - 2026-09-03

### Restored

- Restored the embedded `https://civitai.com` iframe as the primary visual browsing surface after the v22.2 regression.
- Restored the original workflow: browse Civitai, copy a model link, let Sniper/Auto-DL handle acquisition.

### Fixed

- Moved Google/Civitai account login back to a normal browser context instead of forcing OAuth inside the iframe.
- Added **Reload Civitai Panel**.

## [22.2] - 2026-09-03

### Fixed

- Replaced ineffective sequential `ThreadPoolExecutor` usage with real submitted workers.
- Added safe `.part` handling for interrupted downloads.
- Added clearer HTTP 401/403 handling.
- Added unknown/zero `Content-Length` support.
- Sanitized Windows path components.
- Switched API authentication toward Bearer headers instead of appending the key to generated download URLs.

### Experiment / regression

- Removed the iframe and introduced a native API browser to avoid embedded OAuth failures.
- This solved one technical symptom but removed too much of the original product experience and was corrected in v22.3.

## [22.1]

### Changed

- Cleaned HTML from downloaded model descriptions.
- Added Forge-compatible metadata handling.
- Saved model preview images beside downloaded LoRAs.

## [21]

### Added

- Sniper Mode clipboard monitoring.
- Auto-DL zero-click workflow.
- PowerShell clipboard bridge.
- Live download telemetry.
- Retry handling.
- Tag-based LoRA organization.
