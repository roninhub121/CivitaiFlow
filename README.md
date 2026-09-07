# CivitaiFlow v22.4 — Control Deck Edition

> Browse Civitai inside Stable Diffusion WebUI Forge, capture model links from the clipboard, and download LoRAs automatically with API-authenticated transfers.

CivitaiFlow keeps the **real Civitai website embedded inside Forge** as the main discovery experience. Around that panel it adds a compact control deck for Civitai API authentication, Sniper capture, automatic downloads, retry handling, metadata generation, previews, and LoRA organization.

## What changed in v22.4

v22.4 focuses on two things: making API authentication obvious and making the extension feel like a finished product instead of a collection of utility buttons.

### New API Access card

You no longer need to leave the CivitaiFlow tab and hunt through Forge settings just to connect the API.

The left panel now includes:

- masked **API key** input;
- **Connect API** — validates the token against `GET /api/v1/me` and only saves it when valid;
- **Verify** — checks the currently saved key;
- **Get API Key ↗** — opens Civitai Settings in your normal browser;
- **Disconnect** — clears the saved token from Forge;
- connection status with the authenticated Civitai username and a masked token suffix.

The token is persisted using Forge's own configuration system and is sent to Civitai as:

```http
Authorization: Bearer <CIVITAI_API_KEY>
```

CivitaiFlow does not append your token to generated download URLs.

### Tuned interface

The old emoji-heavy dashboard has been replaced by a cleaner control deck:

- custom monochrome CivitaiFlow mark;
- compact version badge;
- card-based layout;
- restrained status indicators;
- cleaner action labels;
- improved spacing and hierarchy;
- premium dark-panel treatment that stays compatible with Forge themes;
- simplified activity terminal;
- larger embedded Civitai workspace.

## How authentication works

There are **two different authentication contexts** in CivitaiFlow.

### 1. Civitai website session

This controls whether the embedded `civitai.com` website itself shows you as signed in.

Google OAuth can reject sign-in attempts that happen inside an iframe, which is why you previously saw an HTTP 403 screen.

For website login:

1. Open Civitai in your normal browser.
2. Sign in with Google/Civitai there.
3. Return to Forge.
4. Click **Reload Panel**.

Browser privacy / third-party-cookie policy may still determine whether that website session is visible inside the embedded frame.

### 2. Civitai API authentication

This is what CivitaiFlow uses for authenticated metadata and gated/private downloads.

It does **not** log the iframe into the website. It gives the extension an API credential.

To connect it:

1. In CivitaiFlow click **Get API Key ↗**.
2. Sign in to Civitai if needed.
3. In Civitai Settings create an API key.
4. Copy the key.
5. Return to Forge and paste it into **API key**.
6. Click **Connect API**.
7. CivitaiFlow calls `GET /api/v1/me`.
8. If Civitai accepts the key, the extension saves it and shows **Connected as <username>**.

You can still manage the same key from **Settings → CivitaiFlow Manager**.

## Intended workflow

The main CivitaiFlow loop remains simple:

1. Browse Civitai in the embedded right-hand panel.
2. Find a LoRA.
3. Copy the model URL or link address.
4. **Sniper capture** detects the clipboard entry.
5. **Auto download** queues it automatically.
6. Activity shows progress and transfer speed.
7. CivitaiFlow writes the LoRA, preview image, and Forge metadata into the Forge LoRA directory.

You can also paste `civitai.com/models/...` URLs or plain model IDs into the capture field.

## Features

- Embedded Civitai browser as the primary discovery UI.
- Inline Civitai API connection and token persistence.
- API identity verification via `/api/v1/me`.
- Windows clipboard Sniper capture.
- Zero-click automatic queueing.
- Real concurrent workers with `ThreadPoolExecutor.submit(...)`.
- `.safetensors.part` temporary files with atomic rename after successful completion.
- Retry queue for failed downloads.
- Windows-safe filenames and tag folders.
- Forge JSON metadata with description, base model, trigger words, Civitai model ID, and version ID.
- Primary preview-image download.
- API tokens sent via Bearer authorization headers.
- Smart activity cleanup: completed entries disappear quickly while failures remain visible longer.

## Installation

1. Open **Stable Diffusion WebUI Forge**.
2. Go to **Extensions → Install from URL**.
3. Paste:

   `https://github.com/roninhub121/CivitaiFlow`

4. Click **Install**.
5. Open **Installed** and click **Apply and restart UI**.

For an existing installation, update CivitaiFlow from Forge and restart the UI.

## Downloads and files

For each model CivitaiFlow:

1. fetches metadata from the Civitai API;
2. selects the first/latest model version returned by the API;
3. locates the primary `.safetensors` file;
4. creates a tag-based directory under Forge's LoRA folder;
5. writes Forge-compatible JSON metadata;
6. downloads a preview image when available;
7. streams the model to `filename.safetensors.part`;
8. renames it to `filename.safetensors` only after a successful transfer.

This prevents interrupted downloads from looking like complete model files.

## Concurrent downloads

The **Concurrent downloads** slider accepts 1–10 workers.

The implementation submits actual background workers:

```python
executor.submit(_download_worker, model_id, api_key)
```

For normal use, 2–5 workers is a sensible range. If Civitai returns HTTP 429 or 503, lower concurrency and retry later.

## Troubleshooting

### Google returns HTTP 403 inside the embedded panel

Use **Open Civitai in Browser ↗**, complete website login in the normal browser, return to Forge, then click **Reload Panel**.

### I am signed into Civitai but the iframe still looks logged out

That is a browser-cookie/session issue, not an API-key issue. Modern browser privacy controls can prevent third-party iframe cookies from being reused. API-authenticated CivitaiFlow downloads still work independently.

### Connect API says the key is rejected

Create a new API key in Civitai Settings and try again. CivitaiFlow does not save a token that fails `/api/v1/me` validation.

### HTTP 401 / 403 during download

The saved API key is missing, invalid, expired, or the asset requires authenticated access.

### HTTP 429

Civitai is rate-limiting requests. Lower **Concurrent downloads** and retry later.

### HTTP 503

Civitai may be temporarily overloaded. Wait and use **Retry failed**.

### Sniper capture is not detecting links

Confirm PowerShell is available and Windows security policy/software is not blocking background `Get-Clipboard` calls.

### A `.safetensors.part` file remains after a crash

Forge/Python may have been terminated before cleanup. It is safe to remove an orphaned `.part` file before retrying.

## Architecture

CivitaiFlow v22.4 uses a hybrid boundary:

- **Civitai iframe** → primary discovery and browsing;
- **normal browser** → Google OAuth, account management, and API-key creation;
- **Civitai REST API** → metadata, identity verification, and downloads;
- **Bearer API key** → authenticated/gated API access;
- **PowerShell subprocess** → isolated Windows clipboard access;
- **ThreadPoolExecutor** → concurrent model transfers;
- **Forge / Gradio** → control deck and live activity.

## Roadmap

- Better diagnostics for iframe session/cookie behavior.
- Checkpoint routing to the correct Forge model directory.
- VAE and Embedding routing.
- Local installed-model gallery.
- Hash verification after download.
- Preview-image normalization/conversion.
- Tensor.art integration.

## Release history

See [`CHANGELOG.md`](CHANGELOG.md).

## Credits

Developed and maintained by **Ronin**.

*In IT we trust.*
