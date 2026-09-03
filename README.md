# CivitaiFlow

> A visual Civitai-to-Forge acquisition bridge for Stable Diffusion WebUI Forge.

CivitaiFlow is designed around a simple workflow: **see a model you want on Civitai, select it with almost no friction, and let Forge handle the rest automatically**.

The intended loop is:

```text
See a model on Civitai
      ↓
Send to Forge / copy model link
      ↓
CivitaiFlow captures it
      ↓
Resolve metadata + duplicate check + authenticated download
      ↓
Save model + preview + Forge metadata
      ↓
Ready in the local Forge model library
```

The visual Civitai experience matters because model discovery is inherently visual: previews, versions, creators, tags, descriptions, and community context are part of deciding what to download. CivitaiFlow keeps that discovery experience while automating the acquisition and local-library work behind it.

## Product goal

CivitaiFlow should make model acquisition feel native to Forge:

- browse the real Civitai experience without constantly switching context;
- see what you are choosing before it enters the local model library;
- capture a model with one click when the optional Browser Bridge is installed;
- retain the original clipboard Sniper workflow as a universal fallback;
- authenticate downloads without exposing tokens in URLs;
- avoid unnecessary repeat downloads when the target model is already present;
- download in the background with useful telemetry;
- leave interrupted transfers as temporary files instead of fake-complete models;
- create local preview and metadata files that Forge can use;
- evolve toward a hash-indexed local library that can prevent duplicates across checkpoints, LoRAs, VAEs, and embeddings.

## Discovery and capture modes

CivitaiFlow treats discovery as a **multi-surface** problem instead of assuming one iframe will always work.

### 1. Embedded Civitai — integrated visual mode

The right side of the CivitaiFlow tab embeds `civitai.com` when the browser and Civitai allow it.

This is the closest experience to the original CivitaiFlow concept: you remain inside Forge while visually browsing Civitai. The embedded site is still controlled by Civitai's framing headers, authentication flow, cookies, CSP, and website implementation, so availability is best-effort rather than a guaranteed API contract.

### 2. Companion Window — authenticated visual fallback

Use **Open Companion Window ↗** to open Civitai as a normal top-level window in the **same browser running Forge**.

This is the recommended surface for:

- Google/Civitai login;
- browsing when the iframe is blocked or logged out;
- account settings;
- normal first-party cookies;
- continuing the same visual CivitaiFlow workflow without depending on iframe authentication.

When the companion window closes, CivitaiFlow attempts to reload the embedded panel. Whether the authenticated website session becomes visible inside the iframe still depends on browser/Civitai cookie and framing policy.

### 3. Browser Bridge — one-click Send to Forge

The optional `browser-extension/` package adds **Send to Forge** directly to Civitai model cards and model detail pages.

Instead of:

```text
Right-click → Copy link address
```

you can use:

```text
Send to Forge
```

The bridge simply writes the canonical Civitai model URL to the clipboard. The existing **Sniper capture + Auto download** pipeline remains authoritative, so there is no second downloader or duplicated acquisition logic.

Because it runs as a browser content script on `https://civitai.com/*` with `all_frames: true`, it can enhance Civitai in both the embedded iframe and the top-level Companion Window when those pages are available.

See [Browser Bridge](browser-extension/README.md) for installation instructions.

### 4. Civitai API — acquisition authentication

The API connection is separate from the website session.

CivitaiFlow sends the configured credential as:

```http
Authorization: Bearer <CIVITAI_API_KEY>
```

The key is used for authenticated metadata and gated model downloads. It **does not create a browser cookie and does not log the embedded Civitai website into your account**.

## Quick start

1. Install CivitaiFlow through **Forge → Extensions → Install from URL**.
2. Use:

   `https://github.com/roninhub121/CivitaiFlow`

3. Apply the extension changes and restart Forge.
4. Open **CivitaiFlow**.
5. Keep **Sniper capture** and **Auto download** enabled.
6. Configure API authentication from the **Civitai connection** card.
7. Browse Civitai in the embedded panel or use **Open Companion Window ↗**.
8. Either:
   - copy a `civitai.com/models/...` link; or
   - install the optional Browser Bridge and click **Send to Forge**.
9. CivitaiFlow queues the model automatically.

## Optional Browser Bridge setup

The Browser Bridge is currently distributed as an unpacked Chromium extension inside this repository.

### Microsoft Edge

1. Open `edge://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the `browser-extension` folder from your local CivitaiFlow installation.
5. Reload Civitai / Forge.

### Google Chrome

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the `browser-extension` folder from your local CivitaiFlow installation.
5. Reload Civitai.

### What it changes

- Model cards expose **Send to Forge** when hovered.
- Model detail pages expose a persistent **Send to Forge** control.
- A successful click briefly changes to **Sent to Forge**.
- The model URL is copied into the clipboard and picked up by Sniper capture.
- `modelVersionId` is preserved when it already exists in the source URL.

The browser bridge never receives your Civitai API key and does not download model files itself.

## API authentication

### Connect with a personal API key

1. Click **Get API Key ↗**.
2. Sign in to Civitai in the top-level browser window.
3. Open the API Keys section on the Civitai Account page.
4. Create a key and copy it.
5. Return to Forge.
6. Paste it into **API key**.
7. Click **Connect API**.

Before saving the key, CivitaiFlow validates it against:

```http
GET https://civitai.com/api/v1/me
```

A successful connection shows the Civitai identity and only a masked suffix of the token.

You can use **Verify** to re-test the saved key or **Disconnect** to remove it from Forge configuration.

### Least privilege

If Civitai offers scoped personal tokens, the current CivitaiFlow feature set only needs identity/model-reading capabilities for normal browsing and downloads. Prefer the smallest scope set that still allows `/api/v1/me`, model metadata, and model downloads.

### Token storage

The key is saved through Forge's own settings/configuration mechanism. CivitaiFlow masks it in the UI, but it does **not** add a separate encrypted secret store. Treat the Forge configuration directory as sensitive.

See [Authentication design](docs/AUTHENTICATION.md) for the complete trust model and OAuth roadmap.

## Duplicate prevention

CivitaiFlow already avoids re-downloading a model when the expected target `.safetensors` file already exists at the resolved local destination.

That is useful but is **not yet a complete global deduplication system**. Filenames and folders can change, and different Civitai versions can legitimately belong to the same model family.

The target design is a local asset index keyed by:

```text
Civitai model ID
Civitai model version ID
SHA-256
local path
asset type
base model
```

That will allow CivitaiFlow to distinguish:

- the exact same file → **ALREADY INSTALLED**;
- the same Civitai model but a different version → **NEW VERSION**;
- a renamed or moved local file with the same hash → **ALREADY INSTALLED**;
- a genuinely new asset → **DOWNLOAD**.

This is especially important as CivitaiFlow expands from LoRAs to checkpoints, VAEs, embeddings, and other Forge assets.

## Why iframe login is unreliable

There are two independent browser restrictions:

1. **Google OAuth does not support arbitrary embedded user-agents/webviews for authorization.** A Google login flow reached from an iframe can fail with `403` / `disallowed_useragent`.
2. **The embedded website controls whether it may be framed at all.** Headers such as `X-Frame-Options` or CSP `frame-ancestors` can prevent Civitai from rendering inside Forge regardless of our code.

Even after logging in successfully in a normal browser window, modern browsers may block or partition third-party cookies inside cross-site iframes. An API key cannot convert an API session into a website cookie session.

Because of that, CivitaiFlow does not try to scrape browser cookies, forge Civitai session cookies, strip security headers, or reverse-proxy the website to defeat framing policy.

The stable design is:

```text
Embedded panel       → integrated visual discovery when allowed
Companion window     → real website login + reliable visual fallback
Browser Bridge       → one-click capture from Civitai cards/pages
Civitai API key      → authenticated metadata + downloads
CivitaiFlow backend  → duplicate checks, transfer, metadata, organization
```

## Current feature set

- Embedded Civitai browser when framing is permitted.
- Same-browser companion window for login and fallback browsing.
- Optional one-click Browser Bridge for Civitai cards and model pages.
- Windows clipboard Sniper capture.
- Zero-click auto queueing.
- Civitai API-key verification through `/api/v1/me`.
- Bearer-token authenticated requests.
- Basic existing-target duplicate prevention.
- Real concurrent downloads through `ThreadPoolExecutor.submit(...)`.
- `.safetensors.part` temporary transfers with atomic rename on success.
- Retry handling for failed transfers.
- Download progress and speed telemetry.
- Windows-safe local filenames.
- Forge JSON metadata with description, base model, activation words, Civitai model ID, and version ID.
- Primary Civitai preview-image download.
- Tag-based LoRA organization.

## Current scope and important limitations

CivitaiFlow is currently optimized for **LoRA acquisition on Windows + Stable Diffusion WebUI Forge**.

The codebase is intentionally small, but several areas are still product work rather than finished infrastructure:

- the iframe is not a guaranteed integration contract with Civitai;
- browser login and API authentication are separate sessions;
- the Browser Bridge depends on Civitai DOM heuristics for per-card placement;
- Sniper capture currently depends on Windows PowerShell `Get-Clipboard`;
- the download engine currently targets the Forge LoRA directory;
- model-type routing for checkpoints, VAEs, embeddings, etc. is not finished;
- copied URLs that target a specific model version need stronger version-aware handling in the Python resolver;
- duplicate detection is currently destination/file based rather than a global SHA-indexed library;
- in-memory activity state is global to the Forge process and assumes a local/single-user installation;
- post-download hash verification is not implemented yet.

See [Architecture](docs/ARCHITECTURE.md) for the engineering audit and target design.

## Download behavior

For a captured model, CivitaiFlow currently:

1. resolves the Civitai model through the REST API;
2. selects a model version;
3. locates a `.safetensors` file;
4. checks whether the expected local target already exists;
5. creates the local target folder when needed;
6. writes Forge-compatible metadata;
7. downloads a preview image when available;
8. streams the model to `*.safetensors.part`;
9. reports progress and transfer speed;
10. atomically renames the temporary file after a successful transfer.

If the process crashes before completion, an orphaned `.part` file can remain and may be deleted before retrying.

## Troubleshooting

### Google returns 403 inside the embedded panel

Do not authenticate Google inside the iframe. Use **Open Companion Window ↗**, sign in there, and continue browsing in that top-level window. Close it and CivitaiFlow will attempt to reload the embedded panel.

### The iframe is blank or reports that Civitai refused to connect

Use **Open Companion Window ↗**. This means the site/browser framing policy is blocking embedded mode; it is not an API-key failure.

### I am logged in in the companion window but the iframe still looks logged out

That can happen when third-party cookies are blocked or partitioned. The website session may not be reusable inside a cross-site iframe. API-authenticated downloads still work independently.

### Send to Forge does not appear on Civitai cards

Confirm the optional Browser Bridge is loaded and enabled in Edge/Chrome, then reload the Civitai page. If Civitai has changed its DOM structure, the bridge's card-placement heuristic may need an update.

### Send to Forge says Copy failed

The browser refused clipboard write access. Confirm the Browser Bridge has clipboard permission, or use the original right-click / copy-link Sniper workflow.

### API key is rejected

Create a new key on the Civitai Account page, paste it into the CivitaiFlow connection card, and click **Connect API**.

### HTTP 401 / 403 during download

The saved API key may be invalid, expired, missing the required scope, or the model may require authentication not available to the current credential.

### HTTP 429 / 503

Reduce **Concurrent downloads**, wait briefly, and use **Retry failed**.

### Sniper capture does not detect links

Confirm PowerShell is available and Windows security policy is not blocking background `Get-Clipboard` calls.

## Architecture

CivitaiFlow is a small Forge extension with four logical layers:

```text
Discovery / visual selection
  ├─ embedded Civitai
  ├─ companion browser window
  └─ optional Browser Bridge buttons
          ↓
Capture layer
  └─ Windows clipboard / pasted URLs
          ↓
Acquisition engine
  ├─ Civitai REST metadata
  ├─ duplicate checks
  ├─ Bearer authentication
  ├─ concurrent transfers
  └─ retry / telemetry
          ↓
Forge integration
  ├─ models/Lora (current primary target)
  ├─ preview image
  └─ JSON metadata
```

Detailed design notes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

Authentication details: [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md)

Browser Bridge: [browser-extension/README.md](browser-extension/README.md)

## Roadmap

Priority direction for the next major release:

- global local-library index and SHA-256 deduplication;
- version-aware URL parsing using `modelVersionId` all the way through resolution and download;
- explicit model-type routing instead of assuming LoRA storage;
- checkpoint / VAE / embedding support;
- SHA-256 verification after downloads;
- installed / new-version state surfaced before queueing a transfer;
- captured-asset card with preview, version, local status, and destination;
- official Civitai OAuth Authorization Code + PKCE login once CivitaiFlow has its own registered OAuth client;
- more durable download queue/state handling;
- optional Windows secure credential storage;
- better diagnostics for iframe/frame-policy failures.

## Security philosophy

CivitaiFlow should integrate with Civitai without defeating browser security boundaries.

The project deliberately avoids:

- scraping Google/Civitai credentials;
- copying browser session cookies into Forge;
- injecting API tokens into Civitai website pages;
- stripping `X-Frame-Options` / CSP from Civitai responses;
- reverse-proxying Civitai solely to bypass anti-framing controls.

The optional Browser Bridge requests Civitai page access and clipboard-write permission only; it does not receive the Forge API token.

The preferred path is explicit browser authentication plus supported API credentials.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Developed and maintained by **Ronin**.

Built for the Stable Diffusion WebUI Forge workflow.
