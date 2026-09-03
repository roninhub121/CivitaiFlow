# Changelog

All notable changes to CivitaiFlow are documented here.

## [22.4.2] - 2026-09-03

### Added

- Added the optional `browser-extension/` **CivitaiFlow Browser Bridge** for Chrome and Microsoft Edge.
- Added one-click **Send to Forge** controls directly on Civitai model cards.
- Added a persistent **Send to Forge** action on Civitai model detail pages.
- The Browser Bridge runs on `https://civitai.com/*` with `all_frames: true`, so it can enhance both the embedded Civitai view and the top-level Companion Window when the browser permits the page to render.
- Successful button clicks copy the canonical Civitai model URL to the clipboard so the existing Sniper capture + Auto Download pipeline is reused unchanged.
- `modelVersionId` is preserved when it is already present in the source URL.
- Added visual `Sent to Forge` and `Copy failed` states with lightweight SVG icons.
- Added `browser-extension/README.md` with Edge/Chrome installation, behavior, security model, and limitations.

### Architecture

- Per-card controls are implemented as an explicit browser content script rather than attempting to reach into the cross-origin Civitai iframe from Forge JavaScript.
- This avoids reverse-proxying Civitai, stripping frame/CSP protections, copying session cookies, or creating a second downloader.
- The browser bridge is intentionally only a capture UX layer; the Forge extension remains authoritative for metadata resolution, duplicate checks, downloads, telemetry, and local organization.

## [22.4.1] - 2026-09-03

### Added

- Added `javascript/civitai_flow.js` as a browser-side Companion Window enhancement.
- The existing **Open Civitai in Browser** action is upgraded client-side to **Open Companion Window ↗**.
- Companion browsing opens Civitai as a normal top-level window in the same browser running Forge.
- Closing the companion window triggers a best-effort reload of the embedded Civitai panel.
- **Get API Key ↗** is upgraded to open the current Civitai Account page (`/user/account`) in the same browser profile.
- Added `docs/ARCHITECTURE.md` with the product objective, deep technical audit, risk register, and target architecture.
- Added `docs/AUTHENTICATION.md` with the browser/API/OAuth trust model and future PKCE design.

### Documentation refresh

- Reframed CivitaiFlow around its actual product goal: **discover on Civitai → capture → resolve → download → organize → use in Forge**.
- Reclassified the iframe as a convenience discovery surface rather than a guaranteed integration contract.
- Documented Companion Window mode as the supported fallback when embedding or iframe authentication fails.
- Documented why an API key authenticates backend downloads but cannot create a Civitai website session.
- Documented Google embedded-user-agent restrictions, anti-framing headers, third-party-cookie behavior, and Storage Access API limitations.
- Documented the official Civitai OAuth Authorization Code + PKCE path as the preferred future replacement for manual API-key copy/paste once CivitaiFlow has its own OAuth client registration.
- Added explicit security guidance against cookie scraping, token-to-cookie injection, header stripping, and reverse-proxy anti-framing bypasses.

### Audit findings recorded

- P0: iframe availability/login is controlled by browser and Civitai policy, not CivitaiFlow.
- P1: download routing currently assumes LoRA storage.
- P1: copied `modelVersionId` intent is not fully preserved by the current resolver.
- P1: API keys are persisted through Forge configuration without CivitaiFlow-specific encryption.
- P2: in-memory state assumes a local/single-user Forge process.
- P2: Sniper clipboard capture is Windows/PowerShell-specific.
- P2: first-tag folder routing is not a durable local taxonomy.
- P2: post-download hash verification is still missing.

## [22.4] - 2026-09-03

### Added

- Inline **Civitai connection** card inside the main CivitaiFlow tab.
- Masked API-key input.
- **Connect API** validates a candidate key against `GET /api/v1/me` before persisting it.
- **Verify** re-tests the currently saved key.
- **Get API Key** opens Civitai account/settings in the browser.
- **Disconnect** removes the saved Civitai API key from Forge configuration.
- Authenticated username display and masked key suffix.
- Inline explanation of the difference between website authentication and API authentication.
- Custom CivitaiFlow SVG mark and version badge.
- Card-based control-deck styling and restrained status indicators.

### Changed

- Reworked the main UI into **Civitai connection**, **Capture & download**, and **Activity** sections.
- Removed most emoji-heavy button labels.
- Increased the embedded Civitai workspace relative to the control column.
- Refined spacing, borders, terminal styling, status presentation, and dark-theme behavior.
- Simplified telemetry strings to `ACTIVE`, `DONE`, and `ERROR` style output.
- Updated the CivitaiFlow user agent to `22.4`.
- Renamed the Forge setting label to **Civitai API Key**.

### Authentication

- API keys are validated before being saved from the CivitaiFlow tab.
- Valid keys are persisted through Forge's `shared.opts.set(...)` + `shared.opts.save(...)` configuration path.
- API authentication uses:

  `Authorization: Bearer <CIVITAI_API_KEY>`

- The API key authenticates CivitaiFlow API/download requests; it does not replace the embedded website's browser session.

## [22.3] - 2026-09-03

### Restored

- Restored the embedded `https://civitai.com` iframe as the primary visual browsing surface after the v22.2 regression.
- Restored the original workflow: browse Civitai, copy a model link, let Sniper/Auto-DL handle acquisition.

### Fixed

- Moved Google/Civitai account login back to a normal browser context instead of forcing OAuth inside the iframe.
- Added **Reload Civitai Panel**.

### Kept from v22.2

- Real concurrent worker submission through `ThreadPoolExecutor.submit(...)`.
- Bearer-token API authentication.
- `.safetensors.part` temporary downloads with atomic rename.
- Improved HTTP 401/403 handling.
- Unknown/zero `Content-Length` handling.
- Windows-safe model/tag filenames.
- Civitai model/version IDs in Forge metadata.
- Preview-image and Forge metadata generation.

## [22.2] - 2026-09-03

### Fixed

- Replaced the ineffective sequential `ThreadPoolExecutor` usage with real submitted workers.
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
