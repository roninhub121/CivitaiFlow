# 📡 CivitaiFlow v22.3 — Hybrid Embed Edition

> A "set & forget" Civitai workflow for Stable Diffusion WebUI Forge: browse Civitai inside Forge, copy model links, and let CivitaiFlow download and organize them automatically.

CivitaiFlow is built around the **embedded Civitai website**. The Civitai panel remains the primary browsing experience; the extension adds clipboard capture, API-key authenticated downloads, concurrent workers, Forge metadata, preview images, retry handling, and automatic LoRA organization around that browser.

## ✨ What changed in v22.3

v22.2 made the wrong product-level tradeoff: it removed the embedded Civitai site entirely in order to avoid Google's OAuth-in-iframe restriction. That fixed one authentication symptom but removed the core workflow CivitaiFlow was designed around.

v22.3 restores the original architecture while keeping the reliability improvements introduced in v22.2:

- **Civitai iframe restored as the main panel.**
- **Google/Civitai login is opened in a normal browser tab** when authentication is required.
- **Reload Civitai Panel** lets you refresh the embedded site after completing login externally.
- **Civitai API key** remains the authentication mechanism for gated/API downloads.
- **Real concurrent downloads** remain enabled through `ThreadPoolExecutor.submit(...)`.
- **`.part` downloads**, safer Windows filenames, improved 401/403 handling, and Forge metadata improvements remain intact.

The important distinction is now explicit:

- **Browsing:** embedded Civitai website inside Forge.
- **Google OAuth / account login:** normal browser tab.
- **Model API/download authentication:** Civitai API key stored in Forge settings.

## 🚀 Features

- **🌐 Embedded Civitai browser** — browse the real Civitai website directly in the CivitaiFlow tab.
- **🎯 Sniper Mode** — watches the Windows clipboard for `civitai.com/models/...` links.
- **⚡ Auto-DL** — automatically queues captured model links.
- **🔐 API Health Check** — validates the configured Civitai API key.
- **🌐 Login / Open Civitai** — opens Civitai in the default browser for login flows that cannot run in an iframe.
- **🔄 Reload Civitai Panel** — refreshes the embedded website after external login or when the panel needs a reload.
- **🧵 Real concurrent downloads** — parallel worker submission through `executor.submit(...)`.
- **🛡️ Safer partial downloads** — downloads into `.safetensors.part` and renames only after success.
- **📂 Auto-organization** — stores LoRAs in tag-based directories.
- **📝 Forge metadata** — writes description, base model, activation words, and Civitai model/version IDs.
- **🖼️ Preview image download** — saves the primary Civitai preview beside the LoRA.
- **🔄 Retry engine** — retries failed downloads from Live Telemetry.
- **🧹 Smart telemetry cleanup** — successful items disappear quickly while errors stay visible longer.

## 🛠️ Installation

1. Open **Stable Diffusion WebUI Forge**.
2. Open **Extensions → Install from URL**.
3. Paste:

   `https://github.com/roninhub121/CivitaiFlow`

4. Click **Install**.
5. Open **Installed** and click **Apply and restart UI**.

For an existing installation, update the extension from Forge and restart the UI.

## 🔐 Configure your Civitai API key

The iframe/browser session and the API key solve different problems. The API key is still required for models/downloads that Civitai gates behind authentication.

1. Click **🌐 Login / Open Civitai** or open Civitai normally in your browser.
2. Sign in to Civitai.
3. Open your Civitai account settings and create an API key.
4. In Forge open **Settings → CivitaiFlow Manager**.
5. Paste the key into **Civitai API Key (Ronin Edition)**.
6. Click **Apply Settings**.
7. Return to **CivitaiFlow** and click **🔐 Check API**.

Expected status:

`🟢 Civitai API connected as ...`

CivitaiFlow sends the key using:

```http
Authorization: Bearer <CIVITAI_API_KEY>
```

The token is not appended to generated model URLs.

## 🌐 Embedded Civitai workflow

The right side of the CivitaiFlow tab is the real Civitai website embedded in Forge.

Typical workflow:

1. Browse Civitai in the embedded panel.
2. Find a LoRA you want.
3. Copy its model URL or link address.
4. **Sniper Mode** detects the clipboard entry.
5. **Auto-DL** queues the model automatically.
6. Live Telemetry shows download progress.
7. The LoRA, preview, and Forge metadata are written under the Forge LoRA directory.

You can also paste a Civitai model URL or plain model ID into the drop zone.

## 🔑 Why Google login still opens externally

Google OAuth can reject authentication attempts performed inside embedded frames/webviews. That is what produced the Google **HTTP 403** screen in earlier builds.

v22.3 does **not** remove the iframe to work around that restriction. Instead it keeps the iframe for the feature it is good at — browsing Civitai — and moves only the unsupported login step to a normal browser tab.

Use this flow when the embedded site asks you to sign in:

1. Click **🌐 Login / Open Civitai**.
2. Complete Google/Civitai login in the normal browser tab.
3. Return to Forge.
4. Click **🔄 Reload Civitai Panel**.

Whether the authenticated website session is visible inside the iframe can also depend on browser third-party-cookie/privacy rules. The API key remains the authoritative authentication path for CivitaiFlow downloads.

## 🎯 Sniper Mode / Zero-click workflow

Keep both options enabled for the intended workflow:

- **🎯 Sniper Mode: ON**
- **⚡ Auto-DL: ON**

CivitaiFlow checks the Windows clipboard through an isolated PowerShell subprocess and detects `civitai.com/models/...` URLs.

## 🧵 Concurrent downloads

The **Concurrent Downloads** slider accepts 1–10 workers.

The current implementation submits real background workers:

```python
executor.submit(_download_worker, model_id, api_key)
```

The older implementation created a `ThreadPoolExecutor` but then called `download_by_id(...)` directly inside a normal loop, which made the work effectively sequential.

For normal use, **2–5 workers** is recommended. If Civitai returns HTTP 429 or 503, reduce concurrency and retry later.

## 📁 Download behavior

For every detected model, CivitaiFlow:

1. Fetches model metadata from the Civitai API.
2. Selects the first/latest model version returned by the API.
3. Finds its primary `.safetensors` model file.
4. Creates a tag-based directory under Forge's LoRA folder.
5. Writes Forge-compatible JSON metadata.
6. Downloads the primary preview image when available.
7. Streams the model into `filename.safetensors.part`.
8. Atomically renames it to `filename.safetensors` after a successful transfer.

This prevents an interrupted transfer from looking like a complete model file.

## 🚑 Troubleshooting

### Google shows HTTP 403 inside the Civitai panel

This is an embedded OAuth restriction, not a CivitaiFlow API-key failure.

Click **🌐 Login / Open Civitai**, complete the login in the normal browser tab, return to Forge, then click **🔄 Reload Civitai Panel**.

### API key rejected

Generate a new key in Civitai, paste it into **Settings → CivitaiFlow Manager**, apply settings, then click **🔐 Check API**.

### HTTP 401 / 403 during model download

The model may require authentication or the configured API key may be invalid/expired.

### HTTP 429

Civitai is rate-limiting requests. Lower **Concurrent Downloads** and retry later.

### HTTP 503

Civitai may be temporarily overloaded. Wait and use **🔄 RETRY FAILED**.

### Sniper Mode is not capturing links

Confirm PowerShell is available and Windows security policy/software is not blocking background `Get-Clipboard` calls.

### `.safetensors.part` remains after a crash

Forge or Python may have terminated before cleanup ran. It is safe to remove an orphaned `.part` file before retrying.

## 🧠 Architecture

CivitaiFlow v22.3 intentionally uses a hybrid architecture:

- **Civitai iframe** → primary discovery/browsing UI.
- **Normal browser** → Google OAuth and account management.
- **Civitai REST API** → metadata and downloads.
- **Bearer API key** → authenticated/gated API access.
- **PowerShell subprocess** → isolated Windows clipboard access.
- **ThreadPoolExecutor** → concurrent transfers.
- **Forge/Gradio** → controls and live telemetry.

## 🗺️ Roadmap

- [ ] Better iframe session/reload diagnostics.
- [ ] Checkpoint routing to the correct Forge model directory.
- [ ] VAE and Embedding routing.
- [ ] Local installed-model gallery.
- [ ] Hash verification after download.
- [ ] Preview-image normalization/conversion.
- [ ] Tensor.art integration.

## 🧾 Release history

See [`CHANGELOG.md`](CHANGELOG.md).

## 👤 Credits

Developed and maintained by **Ronin**.

Architectural design supported by AI tooling.

*In IT we trust.*
