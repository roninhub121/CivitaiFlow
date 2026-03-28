# 📡 CivitaiFlow v21 (Resilience Edition)

> **The definitive "Set & Forget" workflow for LoRA hunters on Stable Diffusion Forge.**

CivitaiFlow is a native extension for **Stable Diffusion WebUI Forge** designed to radically optimize bulk downloading models from Civitai. Forget about downloading manually, moving files into folders, or dealing with memory crashes. This tool automates the entire process: from the moment you copy a link in your browser until the LoRA is ready and tagged on your local drive.

![CivitaiFlow Interface](https://via.placeholder.com/800x400?text=CivitaiFlow+v21+Interface+Preview) 
*(Note: Add your UI screenshot or GIF here!)*

---

## 🚀 Key Features

* **🎯 Sniper Mode (Clipboard Monitor):** Silent clipboard monitoring. If it detects a valid Civitai link, the extension captures it instantly—no pasting required.
* **⚡ Auto-DL (Zero-Click):** Immediate background downloading. There are no "Process" buttons; if you copy it, it downloads it.
* **🛡️ Segfault-Proof Architecture:** Implements memory reading through isolated OS subprocesses (PowerShell Bridge). This completely eliminates `Access Violation` memory crashes commonly found in multithreaded extensions.
* **🔄 Resilience Engine:** Smart handling of API downtimes (HTTP 429, 503). Features a bulk-retry button for downloads that failed due to server saturation.
* **🧹 Smart UI Purge:** Intelligent traffic monitor. Successful downloads are cleared from the screen after **8 seconds**, while errors persist for **60 seconds** for your supervision.
* **📂 Auto-Organization:** Dynamically creates folders based on official Civitai tags (e.g., `Lora/Character`, `Lora/Style`).
* **📝 Forge Integration:** Automatically generates `.json` and `.info` files compatible with Forge to display metadata, preview images, and trigger words.

---

## 🧠 Technical Deep Dive (Architecture)

For power users and developers, CivitaiFlow solves two major issues when creating extensions in Gradio/FastAPI:

1. **The Clipboard Problem (Memory Crashes):** Direct calls to the Windows API using `ctypes` from async Python threads often clash with OS memory locks, causing `python.exe` to crash abruptly. CivitaiFlow solves this by using a **PowerShell Bridge** (`subprocess.check_output`), isolating memory reading in an independent OS process.
2. **Websocket Timeouts:** Instead of saturating the Forge server with constant frontend requests, download states are handled in a global backend dictionary (`ThreadPoolExecutor`), and the UI simply performs a lightweight, passive polling every 1.5 seconds via `gr.Timer`.

---

## 🛠️ Installation

1. Open **Stable Diffusion Forge**.
2. Go to the **Extensions** tab -> **Install from URL**.
3. Paste this repository's URL: `https://github.com/roninhub121/CivitaiFlow`
4. Click **Install**.
5. Go to the **Installed** tab, click **Apply and restart UI** (or close and reopen the command prompt).

---

## ⚙️ Mandatory Configuration (API Key)

Civitai requires authentication to download models, especially those marked as NSFW or Early Access.

1. Go to your [Civitai Settings](https://civitai.com/user/settings).
2. Scroll down to **API Keys** and click **Add API Key**.
3. Copy the generated key.
4. In the Forge UI, go to the **Settings** tab -> **CivitaiFlow Manager**.
5. Paste your key in the text box and click **Apply Settings** at the top.

---

## 📖 How to Use (Zero-Click Workflow)

CivitaiFlow's philosophy is that the interface is only there to be observed.

1. Go to the **CivitaiFlow** tab. You'll see that **Sniper Mode** and **Auto-Download** are enabled by default.
2. Browse Civitai in the right panel (or in your own web browser).
3. **Right-click -> Copy link address** on any model or download button.
4. **Do nothing else.** The link will appear briefly in the ingestion box and move down to the Traffic Monitor, where the download will start immediately.

---

## 🚑 Troubleshooting

* **Error: HTTP 429 (Too Many Requests) or 503:** Civitai servers are overloaded. Wait a few minutes and click the blue `🔄 RETRY FAILED` button. Recommendation: Lower your "Concurrent Threads" to 2 or 3.
* **API Key Error:** Ensure there are no leading or trailing spaces in your API Key within the Forge Settings.
* **Sniper isn't capturing links:** Verify that Windows security policies aren't blocking background PowerShell command execution.

---

## 🗺️ Roadmap (Coming Soon)

- [ ] Extended support for Checkpoints, VAEs, and Embeddings with auto-routing.
- [ ] Tensor.art API integration.
- [ ] Local gallery preview for newly downloaded models directly in the tab.

---

## 👤 Credits
Developed and maintained by **Ronin**.
Architectural design supported by **Gemini AI**.

*In IT we trust.*
