# Changelog

All notable changes to CivitaiFlow are documented here.

## [22.2] - 2026-09-03

### Fixed

- Removed the embedded `https://civitai.com` iframe that caused Google OAuth/login to fail with HTTP 403 inside Forge.
- Replaced iframe-dependent authentication with a supported split architecture:
  - normal system browser for Civitai website login;
  - Civitai API key for API access and gated downloads.
- Fixed the concurrency implementation. Previous code created a `ThreadPoolExecutor` but invoked `download_by_id(...)` directly in a normal loop, so downloads were effectively sequential.
- Added safe `.part` download handling so interrupted transfers are not left looking like complete `.safetensors` files.
- Added clearer handling for HTTP 401/403 authentication failures.
- Added zero-length/unknown `Content-Length` handling to avoid progress calculation errors.
- Sanitized Windows path components before creating tag folders and model filenames.

### Added

- Native Civitai LoRA browser using `GET /api/v1/models`.
- Search by model name.
- Sort options: Highest Rated, Most Downloaded, and Newest.
- Period filters: AllTime, Year, Month, Week, and Day.
- Optional mature/NSFW search flag.
- Search-result selector with model preview, creator, base model, version, description, and direct Civitai link.
- Direct **Download selected LoRA** action from native search results.
- **Check API** action using authenticated `GET /api/v1/me`.
- **Open Civitai** action that launches the system browser.
- Civitai model ID and version ID in generated Forge metadata.
- Real background worker submission via `ThreadPoolExecutor.submit(...)`.

### Changed

- Civitai API authentication now prefers `Authorization: Bearer <token>` headers rather than appending the API key to download URLs.
- The advanced setting label changed from **Concurrent Threads** to **Concurrent Downloads** to reflect actual behavior.
- The main tab identifies itself as **CivitaiFlow v22.2**.
- Documentation now explains the browser-auth/API-auth boundary and why embedded OAuth was removed.

### Security / reliability

- API keys are no longer added to generated model download query strings by CivitaiFlow.
- Model descriptions displayed in the native browser are stripped of HTML and escaped before rendering.
- Remote preview URLs are accepted only when they use HTTPS.
- Partial model files are cleaned up on handled download failures.

## [22.1]

### Changed

- Cleaned HTML from downloaded model descriptions.
- Added Forge-compatible metadata handling.
- Saved model preview images alongside downloaded LoRAs.

## [21]

### Added

- Sniper Mode clipboard monitoring.
- Auto-DL zero-click workflow.
- PowerShell clipboard bridge.
- Live download telemetry.
- Retry handling.
- Tag-based LoRA organization.
