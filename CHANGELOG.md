# Changelog

All notable changes to CivitaiFlow are documented here.

## [22.4] - 2026-09-03

### Added

- Inline **API Access** card inside the main CivitaiFlow tab.
- Masked API-key input.
- **Connect API** action that validates a candidate key against `GET /api/v1/me` before persisting it.
- **Verify** action for the currently saved key.
- **Get API Key** action that opens Civitai Settings in the normal browser.
- **Disconnect** action that removes the saved Civitai API key from Forge configuration.
- Authenticated username display and masked key suffix after a successful connection.
- Inline explanation of the difference between Civitai website authentication and CivitaiFlow API authentication.
- Custom CivitaiFlow SVG mark and version badge.
- Card-based control deck styling and status indicators.

### Changed

- Reworked the main UI into three compact sections: **Civitai connection**, **Capture & download**, and **Activity**.
- Removed most emoji-heavy button labels in favor of cleaner text actions and restrained symbols.
- Increased the embedded Civitai workspace relative to the control column.
- Refined spacing, borders, terminal styling, status presentation, and dark-theme behavior.
- Simplified telemetry strings to `ACTIVE`, `DONE`, and `ERROR` style output instead of decorative emoji states.
- Updated the CivitaiFlow user agent to `22.4`.
- Renamed the Forge setting label to **Civitai API Key**.

### Authentication

- API keys are validated before being saved from the CivitaiFlow tab.
- Valid keys are persisted through Forge's native `shared.opts.set(...)` + `shared.opts.save(...)` configuration path.
- API authentication remains Bearer-token based:

  `Authorization: Bearer <CIVITAI_API_KEY>`

- The API key authenticates CivitaiFlow API/download requests; it does not replace the embedded website's browser session.
- Google/Civitai website login remains a normal-browser operation because Google OAuth can reject iframe/webview authentication.

### Kept

- Embedded Civitai iframe as the primary discovery experience.
- Sniper clipboard capture and Auto Download workflow.
- Real concurrent worker submission through `ThreadPoolExecutor.submit(...)`.
- `.safetensors.part` temporary transfers with atomic rename after success.
- Improved 401/403 handling and unknown `Content-Length` handling.
- Windows-safe model/tag filenames.
- Forge metadata and preview-image generation.

## [22.3] - 2026-09-03

### Restored

- Restored the embedded `https://civitai.com` iframe as the primary CivitaiFlow browsing experience.
- Restored the original product workflow: browse Civitai inside Forge, copy a model link, and let Sniper Mode / Auto-DL handle the download.

### Fixed

- Corrected the v22.2 product regression where the iframe was removed entirely to avoid Google OAuth-in-frame failures.
- Google/Civitai account login is now explicitly opened in a normal browser tab instead of attempting to force OAuth inside the iframe.
- Added **Reload Civitai Panel** so the embedded site can be refreshed after completing login externally.

### Kept from v22.2

- Real concurrent worker submission through `ThreadPoolExecutor.submit(...)`.
- Bearer-token API authentication for Civitai API/download requests.
- `.safetensors.part` temporary download files with atomic rename after success.
- Improved HTTP 401/403 handling.
- Unknown/zero `Content-Length` handling.
- Windows-safe model/tag filenames.
- Civitai model ID and version ID in generated Forge metadata.
- Preview-image and Forge metadata generation.

### Architecture

v22.3 uses a hybrid boundary:

- **iframe:** primary Civitai discovery and browsing;
- **normal browser:** Google OAuth / account login;
- **API key:** authenticated Civitai API calls and gated downloads.

This preserves CivitaiFlow's original embedded experience without pretending that Google OAuth is guaranteed to work inside an iframe. Browser third-party-cookie/privacy policy can still affect whether an external website login session is visible to the embedded Civitai frame.

## [22.2] - 2026-09-03

### Fixed

- Removed the embedded `https://civitai.com` iframe that caused Google OAuth/login to fail with HTTP 403 inside Forge.
- Replaced iframe-dependent authentication with a split architecture:
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

### Security / reliability

- API keys are no longer added to generated model download query strings by CivitaiFlow.
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
