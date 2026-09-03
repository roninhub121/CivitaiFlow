# 📡 CivitaiFlow v22.2 — Native Browser Edition

> A "set & forget" Civitai workflow for Stable Diffusion WebUI Forge, with clipboard capture, background downloads, API-key authentication, and a native Civitai model browser.

CivitaiFlow is a native extension for **Stable Diffusion WebUI Forge** designed to make downloading LoRAs from Civitai fast and low-friction. It can capture model links from the Windows clipboard, queue downloads automatically, organize files, generate Forge metadata, and browse Civitai directly through its API.

## ✨ What's new in v22.2

v22.2 removes the embedded `iframe` browser and replaces it with a **native Civitai browser backed by the Civitai REST API**.

This fixes the login problem where Google returned **HTTP 403** inside Forge. Google OAuth is not designed to run inside arbitrary embedded frames/webviews, and Civitai itself may restrict framing. CivitaiFlow now keeps authentication and browsing on supported paths:

- **Civitai API key** for authenticated API requests and gated downloads.
- **Open Civitai** button for normal browser login.
- **Native API search** inside Forge for discovering LoRAs.
- **No embedded login page and no Civitai iframe.**

The release also fixes the old concurrency implementation. The **Concurrent Downloads** slider now controls real `ThreadPoolExecutor` workers instead of running each download sequentially inside a pool context.

## 🚀 Features

- **🎯 Sniper Mode** — watches the Windows clipboard for `civitai.com/models/...` links.
- **⚡ Auto-DL** — queues captured model links without a separate Process button.
- **🔎 Native Civitai Browser** — searches LoRAs through `GET /api/v1/models`.
- **🔐 API Health Check** — validates the configured key against `GET /api/v1/me`.
- **🌐 External Login** — opens Civitai in the default system browser so OAuth works normally.
- **⬇️ Direct model download** — select a native search result and queue it immediately.
- **🧵 Real concurrent downloads** — actual parallel workers through `executor.submit(...)`.
- **🛡️ Safer partial downloads** — writes to `.part` and atomically renames only after completion.
- **📂 Auto-organization** — stores LoRAs under tag-based folders.
- **📝 Forge metadata** — generates `.json` metadata with description, base model, trigger words, and Civitai IDs.
- **🖼️ Preview image download** — saves the primary model-version preview next to the LoRA.
- **🔄 Retry engine** — retries failed downloads from the live telemetry panel.
- **🧹 Smart telemetry cleanup** — completed entries disappear quickly while errors remain visible longer.

## 🛠️ Installation

1. Open **Stable Diffusion WebUI Forge**.
2. Open **Extensions → Install from URL**.
3. Paste:

   `https://github.com/roninhub121/CivitaiFlow`

4. Click **Install**.
5. Open **Installed** and click **Apply and restart UI**.

For an existing installation, use Forge's extension update flow and restart the UI.

## 🔐 Configure your Civitai API key

Authenticated downloads should use a Civitai API key rather than trying to log in inside Forge.

1. Sign in to Civitai in your normal browser.
2. Open your Civitai account/settings page and create an API key.
3. In Forge open **Settings → CivitaiFlow Manager**.
4. Paste the key into **Civitai API Key (Ronin Edition)**.
5. Click **Apply Settings**.
6. Open the **CivitaiFlow** tab and click **🔐 Check API**.

Expected status:

`🟢 Civitai API connected as ...`

The key is sent as an `Authorization: Bearer ...` header. v22.2 no longer appends the token to model download URLs.

## 🔎 Native Civitai Browser

The right side of the CivitaiFlow tab is now a native browser instead of an iframe.

1. Enter a character, style, concept, or other LoRA search.
2. Choose the sort order and time period.
3. Optionally enable mature/NSFW results.
4. Click **Search**.
5. Choose a result from the dropdown.
6. Review its preview, creator, base model, version, and description.
7. Click **⬇️ Download selected LoRA**.

The preview includes an **Open model on Civitai ↗** link that opens the real site in a normal browser tab.

## 🎯 Sniper Mode / Zero-click workflow

The original workflow is still available.

1. Keep **🎯 Sniper Mode** enabled.
2. Keep **⚡ Auto-DL** enabled.
3. Browse Civitai in Chrome, Edge, Firefox, or another normal browser.
4. Copy a Civitai model URL.
5. CivitaiFlow detects the URL from the clipboard and queues the model.

You can also paste a Civitai model URL or plain model ID into the drop zone.

## 🧵 Concurrent downloads

The **Concurrent Downloads** slider accepts values from 1 to 10.

v22.2 uses real worker submissions:

```python
executor.submit(_download_worker, model_id, api_key)
```

The older implementation created a `ThreadPoolExecutor` but called `download_by_id(...)` directly inside a normal loop, so the work was effectively sequential.

For normal use, **2–5 workers** is recommended. If Civitai starts returning HTTP 429 or 503, reduce the concurrency and retry later.

## 📁 Download behavior

For every selected model, CivitaiFlow:

1. Fetches model metadata from Civitai.
2. Selects the latest model version returned by the API.
3. Locates its primary `.safetensors` model file.
4. Creates a tag-based folder under Forge's LoRA directory.
5. Writes Forge metadata.
6. Downloads a preview image when available.
7. Streams the model into `filename.safetensors.part`.
8. Renames the file to `filename.safetensors` only when the transfer completes.

This prevents an interrupted transfer from looking like a complete LoRA.

## 🔒 Authentication architecture

CivitaiFlow deliberately separates the two authentication contexts:

### Browser authentication

Used for:

- Google login.
- Civitai website sessions.
- Account/settings management.
- Creating API keys.

This happens in the user's **normal web browser**.

### API authentication

Used by CivitaiFlow for:

- API-key validation.
- Authenticated model metadata.
- Gated downloads.
- Authenticated Civitai browsing.

This happens through HTTP requests from the Forge extension using:

```http
Authorization: Bearer <CIVITAI_API_KEY>
```

### Why the iframe was removed

Previous versions rendered:

```html
<iframe src="https://civitai.com"></iframe>
```

That approach caused authentication failures because third-party OAuth and framing policies are outside the extension's control. v22.2 does not attempt to bypass those protections; it uses the supported browser + API-key architecture instead.

## 🚑 Troubleshooting

**Google shows HTTP 403**

Update to v22.2 and restart Forge. Do not try to authenticate inside an embedded Civitai page. Click **🌐 Open Civitai** and sign in through your regular browser.

**API key rejected**

Generate a new key in Civitai, paste it into **Settings → CivitaiFlow Manager**, apply settings, then click **🔐 Check API**.

**HTTP 401 / 403 during download**

The model may require authentication or the configured key may be invalid/expired.

**HTTP 429**

Civitai is rate-limiting requests. Lower **Concurrent Downloads** and retry later.

**HTTP 503**

Civitai may be temporarily overloaded. Wait and use **🔄 RETRY FAILED**.

**Sniper Mode is not capturing links**

Confirm that PowerShell is available and Windows policy/security software is not blocking background `Get-Clipboard` calls.

**A `.part` file remains after an abnormal process termination**

Forge or Python may have been terminated before CivitaiFlow could clean the temporary download. It is safe to remove an orphaned `.safetensors.part` file before retrying.

## 🧠 Architecture notes

CivitaiFlow intentionally keeps its moving parts small:

- **Forge / Gradio UI** for controls and telemetry.
- **Civitai REST API** for search and metadata.
- **Bearer token** for authenticated API calls.
- **PowerShell subprocess** for isolated clipboard access on Windows.
- **ThreadPoolExecutor** for concurrent model transfers.
- **In-memory download registry** for lightweight telemetry.
- **System browser** for website login instead of embedded OAuth.

## 🗺️ Roadmap

- [ ] Checkpoint routing to the correct Forge model directory.
- [ ] VAE and Embedding routing.
- [ ] Base-model filters in the native browser.
- [ ] Cursor-based pagination / Load More.
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
