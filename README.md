# CivitaiFlow

> A Civitai-to-Forge acquisition bridge for Stable Diffusion WebUI Forge.

CivitaiFlow is not primarily an embedded web browser. Its real job is to remove the friction between **discovering a model on Civitai** and **having that model ready to use locally in Forge**.

The intended loop is:

```text
Discover on Civitai
      ↓
Copy a model link
      ↓
CivitaiFlow captures it
      ↓
Resolve metadata + authenticated download
      ↓
Save model + preview + Forge metadata
      ↓
Ready in the local Forge model library
```

The embedded Civitai panel is a convenience layer around that loop. Sniper capture, API-authenticated transfers, download resilience, local organization, and Forge integration are the core of the extension.

## Product goal

CivitaiFlow should make model acquisition feel native to Forge:

- browse Civitai without constantly switching context;
- capture Civitai model links with minimal interaction;
- authenticate downloads without exposing tokens in URLs;
- download in the background with useful telemetry;
- leave interrupted transfers as temporary files instead of fake-complete models;
- create local preview and metadata files that Forge can use;
- keep the workflow useful even when Civitai changes its website or browser policies.

## Discovery modes

CivitaiFlow now treats discovery as a **multi-surface** problem instead of assuming one iframe will always work.

### 1. Embedded Civitai — convenience mode

The right side of the CivitaiFlow tab embeds `civitai.com` when the browser and Civitai allow it.

This is the closest experience to the original CivitaiFlow concept, but it is inherently best-effort. Civitai controls its own framing headers, authentication flow, cookies, CSP, and website implementation. Those policies can change independently of this extension.

### 2. Companion Window — authenticated fallback

Use **Open Companion Window ↗** to open Civitai as a normal top-level window in the **same browser running Forge**.

This is the recommended surface for:

- Google/Civitai login;
- browsing when the iframe is blocked or logged out;
- account settings;
- normal first-party cookies;
- continuing the Sniper workflow without depending on iframe authentication.

The companion window is still part of the same workflow: browse Civitai there, copy a model link, and CivitaiFlow continues capturing it from the Windows clipboard.

When the companion window closes, CivitaiFlow attempts to reload the embedded panel. Whether the authenticated website session becomes visible inside the iframe still depends on browser/Civitai cookie and framing policy.

### 3. Civitai API — download authentication

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
8. Copy a `civitai.com/models/...` link.
9. CivitaiFlow queues the model automatically.

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

## Why iframe login is unreliable

There are two independent browser restrictions:

1. **Google OAuth does not support arbitrary embedded user-agents/webviews for authorization.** A Google login flow reached from an iframe can fail with `403` / `disallowed_useragent`.
2. **The embedded website controls whether it may be framed at all.** Headers such as `X-Frame-Options` or CSP `frame-ancestors` can prevent Civitai from rendering inside Forge regardless of our code.

Even after logging in successfully in a normal browser window, modern browsers may block or partition third-party cookies inside cross-site iframes. An API key cannot convert an API session into a website cookie session.

Because of that, CivitaiFlow does not try to scrape browser cookies, forge Civitai session cookies, strip security headers, or reverse-proxy the website to defeat framing policy.

The stable design is:

```text
Embedded panel       → convenient discovery when allowed
Companion window     → real website login + reliable browsing fallback
Civitai API key      → authenticated metadata + downloads
CivitaiFlow backend  → capture, transfer, metadata, organization
```

## Current feature set

- Embedded Civitai browser when framing is permitted.
- Same-browser companion window for login and fallback browsing.
- Windows clipboard Sniper capture.
- Zero-click auto queueing.
- Civitai API-key verification through `/api/v1/me`.
- Bearer-token authenticated requests.
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
- Sniper capture currently depends on Windows PowerShell `Get-Clipboard`;
- the download engine currently targets the Forge LoRA directory;
- model-type routing for checkpoints, VAEs, embeddings, etc. is not finished;
- copied URLs that target a specific model version need stronger version-aware handling;
- in-memory activity state is global to the Forge process and assumes a local/single-user installation;
- post-download hash verification is not implemented yet.

See [Architecture](docs/ARCHITECTURE.md) for the engineering audit and target design.

## Download behavior

For a captured model, CivitaiFlow currently:

1. resolves the Civitai model through the REST API;
2. selects a model version;
3. locates a `.safetensors` file;
4. creates the local target folder;
5. writes Forge-compatible metadata;
6. downloads a preview image when available;
7. streams the model to `*.safetensors.part`;
8. reports progress and transfer speed;
9. atomically renames the temporary file after a successful transfer.

If the process crashes before completion, an orphaned `.part` file can remain and may be deleted before retrying.

## Troubleshooting

### Google returns 403 inside the embedded panel

Do not authenticate Google inside the iframe. Use **Open Companion Window ↗**, sign in there, and continue browsing in that top-level window. Close it and CivitaiFlow will attempt to reload the embedded panel.

### The iframe is blank or reports that Civitai refused to connect

Use **Open Companion Window ↗**. This means the site/browser framing policy is blocking embedded mode; it is not an API-key failure.

### I am logged in in the companion window but the iframe still looks logged out

That can happen when third-party cookies are blocked or partitioned. The website session may not be reusable inside a cross-site iframe. API-authenticated downloads still work independently.

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
Discovery surfaces
  ├─ embedded Civitai
  └─ companion browser window
          ↓
Capture layer
  └─ Windows clipboard / pasted URLs
          ↓
Acquisition engine
  ├─ Civitai REST metadata
  ├─ Bearer authentication
  ├─ concurrent transfers
  └─ retry / telemetry
          ↓
Forge integration
  ├─ models/Lora
  ├─ preview image
  └─ JSON metadata
```

Detailed design notes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

Authentication details: [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md)

## Roadmap

Priority direction for the next major release:

- official Civitai OAuth Authorization Code + PKCE login once CivitaiFlow has its own registered OAuth client;
- version-aware URL parsing using `modelVersionId`;
- explicit model-type routing instead of assuming LoRA storage;
- checkpoint / VAE / embedding support;
- SHA-256 verification after downloads;
- more durable download queue/state handling;
- optional Windows secure credential storage;
- better diagnostics for iframe/frame-policy failures;
- local installed-model inventory and update detection;
- optional Civitai companion/browser integration beyond clipboard capture.

## Security philosophy

CivitaiFlow should integrate with Civitai without defeating browser security boundaries.

The project deliberately avoids:

- scraping Google/Civitai credentials;
- copying browser session cookies into Forge;
- injecting API tokens into Civitai website pages;
- stripping `X-Frame-Options` / CSP from Civitai responses;
- reverse-proxying Civitai solely to bypass anti-framing controls.

The preferred path is explicit browser authentication plus supported API credentials.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Developed and maintained by **Ronin**.

Built for the Stable Diffusion WebUI Forge workflow.
