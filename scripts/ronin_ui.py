import os
import requests
import json
import re
import time
import threading
import subprocess
import webbrowser
import html
import modules.scripts as scripts
import gradio as gr
from modules import paths, shared, script_callbacks
from concurrent.futures import ThreadPoolExecutor

LORA_DIR = os.path.join(paths.models_path, "Lora")
CIVITAI_BASE_URL = "https://civitai.com"
CIVITAI_API_URL = f"{CIVITAI_BASE_URL}/api/v1"

# --- GLOBAL STATE ---
DOWNLOAD_STATUS = {}
EXPIRATION_REGISTRY = {}
ACTIVE_TASKS = 0
TASK_LOCK = threading.Lock()
LAST_CLIPBOARD = ""
PROCESSED_IDS = set()
FAILED_IDS = set()


def on_ui_settings():
    section = ("civitai_flow", "CivitaiFlow Manager")
    shared.opts.add_option(
        "civitai_api_key",
        shared.OptionInfo(
            "",
            "Civitai API Key (Ronin Edition)",
            gr.Textbox,
            {"visible": True},
            section=section,
        ),
    )


script_callbacks.on_ui_settings(on_ui_settings)


def get_api_key():
    return str(shared.opts.data.get("civitai_api_key", "") or "").strip()


def build_headers(api_key=None):
    api_key = (api_key if api_key is not None else get_api_key()).strip()
    headers = {"User-Agent": "CivitaiFlow/22.3 (Stable Diffusion Forge)"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def initial_api_status():
    if get_api_key():
        return "🟠 **API key configured.** Click **Check API** to validate it."
    return "🟡 **API key missing.** Browsing still works in the embedded Civitai panel; gated downloads require a key."


def check_api_status():
    api_key = get_api_key()
    if not api_key:
        return (
            "🟡 **API key missing.** Add one in **Settings → CivitaiFlow Manager**, "
            "apply settings, then check again."
        )

    try:
        response = requests.get(
            f"{CIVITAI_API_URL}/me",
            headers=build_headers(api_key),
            timeout=15,
        )
        if response.status_code == 200:
            data = response.json()
            username = data.get("username") or data.get("name") or data.get("id") or "authenticated user"
            return f"🟢 **Civitai API connected** as `{username}`."
        if response.status_code in (401, 403):
            return "🔴 **API key rejected.** Generate a new key in Civitai and save it in Forge settings."
        return f"🟠 **Civitai API responded with HTTP {response.status_code}.**"
    except requests.RequestException as exc:
        return f"🔴 **Could not reach Civitai API:** `{html.escape(str(exc)[:120])}`"


def get_windows_clipboard():
    try:
        clip_bytes = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Clipboard",
            ],
            creationflags=0x08000000,
            timeout=2,
        )
        text = clip_bytes.decode("utf-8", errors="ignore").strip()
        if len(text) > 300 or "$uiCode" in text or "import os" in text:
            return ""
        return text
    except Exception:
        return ""


def parse_civitai_urls(text):
    text = text or ""
    matches = re.findall(r"models/(\d+)", text)
    numbers = re.findall(r"^\d+$", text, re.MULTILINE)
    return list(dict.fromkeys(matches + numbers))


def safe_filename_component(value, fallback="General"):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "")).strip(" .")
    return value[:120] or fallback


def strip_html(value):
    return re.sub(r"<[^>]+>", "", value or "").strip()


def download_by_id(model_id, api_key):
    global DOWNLOAD_STATUS, FAILED_IDS

    tracker_name = f"ID: {model_id}"
    DOWNLOAD_STATUS[tracker_name] = "🔄 Connecting..."
    headers = build_headers(api_key)

    try:
        response = requests.get(
            f"{CIVITAI_API_URL}/models/{model_id}",
            headers=headers,
            timeout=20,
        )
        if response.status_code != 200:
            if response.status_code in (401, 403):
                DOWNLOAD_STATUS[tracker_name] = "❌ Authentication required or API key rejected"
            else:
                DOWNLOAD_STATUS[tracker_name] = f"❌ API Error: {response.status_code}"
            FAILED_IDS.add(model_id)
            return

        model_data = response.json()
        versions = model_data.get("modelVersions") or []
        if not versions:
            DOWNLOAD_STATUS[tracker_name] = "❌ No downloadable model versions found"
            FAILED_IDS.add(model_id)
            return

        version = versions[0]
        files_list = version.get("files") or []
        primary_file = next(
            (
                file_info
                for file_info in files_list
                if file_info.get("type") == "Model"
                and str(file_info.get("name", "")).lower().endswith(".safetensors")
            ),
            None,
        )
        if not primary_file:
            DOWNLOAD_STATUS[tracker_name] = "❌ No .safetensors model file found"
            FAILED_IDS.add(model_id)
            return

        download_url = primary_file.get("downloadUrl") or (
            f"{CIVITAI_BASE_URL}/api/download/models/{version['id']}"
        )
    except (requests.RequestException, ValueError, KeyError) as exc:
        DOWNLOAD_STATUS[tracker_name] = f"❌ Error: {str(exc)[:80]}"
        FAILED_IDS.add(model_id)
        return

    clean_name = safe_filename_component(model_data.get("name"), tracker_name)
    DOWNLOAD_STATUS.pop(tracker_name, None)
    tracker_name = clean_name

    tag = (model_data.get("tags") or ["General"])[0]
    target_dir = os.path.join(LORA_DIR, safe_filename_component(tag))
    os.makedirs(target_dir, exist_ok=True)

    safetensors_path = os.path.join(target_dir, f"{clean_name}.safetensors")
    partial_path = f"{safetensors_path}.part"

    if os.path.exists(safetensors_path):
        DOWNLOAD_STATUS[tracker_name] = "⏭️ Already exists"
        FAILED_IDS.discard(model_id)
        return

    try:
        forge_json = {
            "description": strip_html(model_data.get("description", "")),
            "sd version": version.get("baseModel", "Unknown"),
            "activation text": ", ".join(version.get("trainedWords", [])),
            "preferred weight": 1.0,
            "civitai model id": model_data.get("id"),
            "civitai version id": version.get("id"),
        }
        with open(
            os.path.join(target_dir, f"{clean_name}.json"),
            "w",
            encoding="utf-8",
        ) as file_handle:
            json.dump(forge_json, file_handle, indent=4, ensure_ascii=False)

        if version.get("images"):
            try:
                image_url = version["images"][0].get("url")
                if image_url:
                    image_response = requests.get(
                        image_url,
                        headers={"User-Agent": headers["User-Agent"]},
                        timeout=20,
                    )
                    if image_response.status_code == 200:
                        with open(
                            os.path.join(target_dir, f"{clean_name}.png"),
                            "wb",
                        ) as file_handle:
                            file_handle.write(image_response.content)
            except (requests.RequestException, OSError, KeyError):
                pass

        with requests.get(
            download_url,
            headers=headers,
            stream=True,
            timeout=600,
        ) as download_response:
            if download_response.status_code != 200:
                if download_response.status_code in (401, 403):
                    DOWNLOAD_STATUS[tracker_name] = "❌ Download requires a valid Civitai API key"
                else:
                    DOWNLOAD_STATUS[tracker_name] = f"❌ HTTP {download_response.status_code}"
                FAILED_IDS.add(model_id)
                return

            total_size = int(download_response.headers.get("content-length", 0) or 0)
            downloaded_bytes = 0
            started_at = time.time()

            with open(partial_path, "wb") as file_handle:
                for chunk in download_response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    file_handle.write(chunk)
                    downloaded_bytes += len(chunk)

                    elapsed = max(time.time() - started_at, 0.001)
                    speed = (downloaded_bytes / (1024 * 1024)) / elapsed
                    if total_size > 0:
                        progress = min((downloaded_bytes / total_size) * 100, 100)
                        DOWNLOAD_STATUS[tracker_name] = f"⬇️ {progress:.1f}% | {speed:.1f} MB/s"
                    else:
                        downloaded_mb = downloaded_bytes / (1024 * 1024)
                        DOWNLOAD_STATUS[tracker_name] = f"⬇️ {downloaded_mb:.1f} MB | {speed:.1f} MB/s"

        os.replace(partial_path, safetensors_path)
        DOWNLOAD_STATUS[tracker_name] = "✅ OK"
        FAILED_IDS.discard(model_id)
    except (requests.RequestException, OSError, ValueError) as exc:
        try:
            if os.path.exists(partial_path):
                os.remove(partial_path)
        except OSError:
            pass
        DOWNLOAD_STATUS[tracker_name] = f"❌ Error: {str(exc)[:80]}"
        FAILED_IDS.add(model_id)


def _download_worker(model_id, api_key):
    global ACTIVE_TASKS
    try:
        download_by_id(model_id, api_key)
    finally:
        with TASK_LOCK:
            ACTIVE_TASKS = max(0, ACTIVE_TASKS - 1)


def start_downloads(model_ids, threads, force=False):
    global ACTIVE_TASKS, PROCESSED_IDS

    normalized_ids = [str(model_id).strip() for model_id in model_ids if str(model_id).strip()]
    if not normalized_ids:
        return 0

    max_workers = max(1, min(int(threads), 10))
    api_key = get_api_key()

    with TASK_LOCK:
        accepted = []
        for model_id in normalized_ids:
            if force or model_id not in PROCESSED_IDS:
                PROCESSED_IDS.add(model_id)
                accepted.append(model_id)
        ACTIVE_TASKS += len(accepted)

    if not accepted:
        return 0

    def run_pool(ids):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(_download_worker, model_id, api_key)
                for model_id in ids
            ]
            for future in futures:
                try:
                    future.result()
                except Exception:
                    pass

    threading.Thread(target=run_pool, args=(accepted,), daemon=True).start()
    return len(accepted)


def master_tick(current_text, is_sniper, is_auto, threads):
    global LAST_CLIPBOARD, DOWNLOAD_STATUS, EXPIRATION_REGISTRY

    current_text = current_text or ""
    text_update = gr.update()

    if is_sniper:
        clip = get_windows_clipboard()
        if clip and "civitai.com/models/" in clip and clip != LAST_CLIPBOARD:
            LAST_CLIPBOARD = clip
            if clip not in current_text:
                current_text = (
                    current_text.strip() + "\n" + clip
                    if current_text.strip()
                    else clip
                )
                text_update = current_text

    if is_auto:
        queued = start_downloads(parse_civitai_urls(current_text), threads)
        if queued:
            text_update = ""

    now = time.time()
    for name, status in list(DOWNLOAD_STATUS.items()):
        is_error = "❌" in status
        ttl = 60 if is_error else 8

        if "✅ OK" in status or "⏭️ Already exists" in status or is_error:
            if name not in EXPIRATION_REGISTRY:
                EXPIRATION_REGISTRY[name] = now
            elif now - EXPIRATION_REGISTRY[name] > ttl:
                DOWNLOAD_STATUS.pop(name, None)
                EXPIRATION_REGISTRY.pop(name, None)

    if ACTIVE_TASKS > 0 or DOWNLOAD_STATUS:
        log_out = []
        if ACTIVE_TASKS > 0:
            log_out.append(f"📊 ACTIVE DOWNLOADS: {ACTIVE_TASKS}\n" + "-" * 30)
        log_out.extend(
            [f"📦 {name[:35]}\n  └ {status}\n" for name, status in DOWNLOAD_STATUS.items()]
        )
        return text_update, "\n".join(log_out)

    return text_update, "😴 System on standby... Copy a Civitai link to wake up."


def retry_failed(threads):
    if not FAILED_IDS:
        return "✅ No failed downloads to retry."

    to_retry = list(FAILED_IDS)
    queued = start_downloads(to_retry, threads, force=True)
    return f"🔄 Retrying {queued} failed download(s)..."


def reset_all():
    global LAST_CLIPBOARD
    with TASK_LOCK:
        DOWNLOAD_STATUS.clear()
        PROCESSED_IDS.clear()
        EXPIRATION_REGISTRY.clear()
        FAILED_IDS.clear()
        LAST_CLIPBOARD = ""
    return "", "🗑️ Monitor cleared."


def open_loras():
    os.makedirs(LORA_DIR, exist_ok=True)
    try:
        os.startfile(LORA_DIR)
        return f"📂 Opened `{LORA_DIR}`."
    except OSError as exc:
        return f"❌ Could not open LoRA directory: `{html.escape(str(exc)[:120])}`"


def open_civitai():
    try:
        opened = webbrowser.open_new_tab(CIVITAI_BASE_URL)
        if opened:
            return (
                "🌐 Opened Civitai in your normal browser. Complete Google/Civitai login there, "
                "then return to Forge and reload the embedded panel."
            )
        return "🟠 Browser did not acknowledge the request. Open `https://civitai.com` manually."
    except Exception as exc:
        return f"❌ Could not open browser: `{html.escape(str(exc)[:120])}`"


def build_civitai_frame(cache_buster=None):
    suffix = f"?cf_reload={cache_buster}" if cache_buster else ""
    return (
        f'<iframe src="{CIVITAI_BASE_URL}/{suffix}" '
        'style="width:100%;height:92vh;border:1px solid #30363d;border-radius:12px;'
        'box-shadow:0 4px 6px rgba(0,0,0,0.3);background:#0d1117;" '
        'referrerpolicy="strict-origin-when-cross-origin" '
        'allow="clipboard-read; clipboard-write; fullscreen" '
        'loading="eager"></iframe>'
    )


def reload_civitai_frame():
    return build_civitai_frame(int(time.time()))


def on_ui_tabs():
    custom_css = """
    #cf_terminal textarea {
        background-color: #0d1117 !important;
        color: #58a6ff !important;
        font-family: 'Consolas', 'Courier New', monospace !important;
        border-radius: 8px !important;
        border: 1px solid #30363d !important;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
    }
    #cf_dropzone textarea {
        background-color: transparent !important;
        border: 2px dashed #4b5563 !important;
        border-radius: 8px !important;
        text-align: center;
    }
    #cf_clear_btn {
        min-width: auto !important;
        padding: 0 10px !important;
    }
    """

    with gr.Blocks(analytics_enabled=False, css=custom_css) as cf_tab:
        timer = gr.Timer(1.5)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 📡 CivitaiFlow v22.3")
                gr.Markdown(
                    "**Embedded Civitai is the primary workflow.** Google OAuth must be completed "
                    "in a normal browser tab because Google blocks sign-in inside embedded frames."
                )
                api_status = gr.Markdown(initial_api_status())

                with gr.Row():
                    btn_check_api = gr.Button("🔐 Check API", variant="secondary")
                    btn_open_civitai = gr.Button("🌐 Login / Open Civitai", variant="secondary")

                btn_reload_frame = gr.Button("🔄 Reload Civitai Panel", variant="secondary")

                with gr.Group():
                    with gr.Row(variant="panel"):
                        sniper = gr.Checkbox(label="🎯 Sniper Mode", value=True)
                        auto = gr.Checkbox(label="⚡ Auto-DL", value=True)

                    url_box = gr.Textbox(
                        label="",
                        lines=2,
                        placeholder="📥 Links drop zone (Sniper Active)",
                        elem_id="cf_dropzone",
                        show_label=False,
                    )

                    btn_folder = gr.Button("📂 Open LoRAs Directory", variant="secondary")

                with gr.Accordion("⚙️ Advanced Settings", open=False):
                    th_slider = gr.Slider(
                        1,
                        10,
                        5,
                        step=1,
                        label="Concurrent Downloads",
                    )

                gr.Markdown("<br>")

                with gr.Row():
                    gr.Markdown("### 📊 Live Telemetry")
                    btn_clear = gr.Button(
                        "🗑️ Clear Log",
                        variant="secondary",
                        elem_id="cf_clear_btn",
                    )

                btn_retry = gr.Button("🔄 RETRY FAILED", variant="primary")

                log_box = gr.Textbox(
                    label="",
                    show_label=False,
                    lines=20,
                    interactive=False,
                    elem_id="cf_terminal",
                )

                action_status = gr.Markdown()

            with gr.Column(scale=5):
                civitai_frame = gr.HTML(build_civitai_frame())

        timer.tick(
            fn=master_tick,
            inputs=[url_box, sniper, auto, th_slider],
            outputs=[url_box, log_box],
        )
        btn_clear.click(fn=reset_all, outputs=[url_box, log_box])
        btn_retry.click(fn=retry_failed, inputs=[th_slider], outputs=[action_status])
        btn_folder.click(fn=open_loras, outputs=[action_status])
        btn_open_civitai.click(fn=open_civitai, outputs=[action_status])
        btn_check_api.click(fn=check_api_status, outputs=[api_status])
        btn_reload_frame.click(fn=reload_civitai_frame, outputs=[civitai_frame])

    return [(cf_tab, "CivitaiFlow", "cf_tab")]


script_callbacks.on_ui_tabs(on_ui_tabs)
