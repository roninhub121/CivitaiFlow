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
CIVITAI_SETTINGS_URL = f"{CIVITAI_BASE_URL}/user/settings"

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
            "Civitai API Key",
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
    headers = {"User-Agent": "CivitaiFlow/22.4 (Stable Diffusion Forge)"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def mask_key(api_key):
    api_key = str(api_key or "").strip()
    if not api_key:
        return "Not configured"
    if len(api_key) <= 8:
        return "••••••••"
    return f"••••••••{api_key[-4:]}"


def status_html(kind, title, detail=""):
    detail_html = f'<span class="cf-status-detail">{html.escape(detail)}</span>' if detail else ""
    return (
        f'<div class="cf-status cf-status-{kind}">'
        '<span class="cf-status-dot" aria-hidden="true"></span>'
        f'<span class="cf-status-copy"><strong>{html.escape(title)}</strong>{detail_html}</span>'
        "</div>"
    )


def initial_api_status():
    api_key = get_api_key()
    if api_key:
        return status_html(
            "warn",
            "API key saved",
            f"{mask_key(api_key)} · Use Connect / Verify to confirm access.",
        )
    return status_html(
        "muted",
        "API access not configured",
        "The embedded site still works. Private or gated downloads need a Civitai API key.",
    )


def _validate_api_key(api_key):
    api_key = str(api_key or "").strip()
    if not api_key:
        return False, None, "Paste a Civitai API key first."

    try:
        response = requests.get(
            f"{CIVITAI_API_URL}/me",
            headers=build_headers(api_key),
            timeout=15,
        )
        if response.status_code == 200:
            data = response.json()
            username = (
                data.get("username")
                or data.get("name")
                or data.get("id")
                or "authenticated user"
            )
            return True, str(username), None
        if response.status_code in (401, 403):
            return False, None, "Civitai rejected this API key."
        return False, None, f"Civitai returned HTTP {response.status_code}."
    except (requests.RequestException, ValueError) as exc:
        return False, None, f"Could not reach Civitai API: {str(exc)[:120]}"


def check_api_status():
    api_key = get_api_key()
    valid, username, error = _validate_api_key(api_key)
    if valid:
        return status_html(
            "ok",
            f"Connected as {username}",
            f"API authentication active · {mask_key(api_key)}",
        )
    if not api_key:
        return status_html(
            "muted",
            "API access not configured",
            "Paste a key below, then click Connect API.",
        )
    return status_html("error", "API connection failed", error or "Unknown error.")


def save_and_connect_api(api_key):
    api_key = str(api_key or "").strip()
    valid, username, error = _validate_api_key(api_key)

    if not valid:
        return (
            status_html("error", "API key not saved", error or "Validation failed."),
            gr.update(value=api_key),
        )

    try:
        shared.opts.set("civitai_api_key", api_key)
        shared.opts.save(shared.config_filename)
    except Exception as exc:
        return (
            status_html(
                "error",
                "Connected, but could not persist the key",
                str(exc)[:120],
            ),
            gr.update(value=api_key),
        )

    return (
        status_html(
            "ok",
            f"Connected as {username}",
            f"API key saved in Forge · {mask_key(api_key)}",
        ),
        gr.update(value=""),
    )


def disconnect_api():
    try:
        shared.opts.set("civitai_api_key", "")
        shared.opts.save(shared.config_filename)
    except Exception as exc:
        return status_html("error", "Could not clear API key", str(exc)[:120]), gr.update()

    return (
        status_html(
            "muted",
            "API access disconnected",
            "Embedded browsing remains available; gated downloads will require a key.",
        ),
        gr.update(value=""),
    )


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
    DOWNLOAD_STATUS[tracker_name] = "Connecting..."
    headers = build_headers(api_key)

    try:
        response = requests.get(
            f"{CIVITAI_API_URL}/models/{model_id}",
            headers=headers,
            timeout=20,
        )
        if response.status_code != 200:
            if response.status_code in (401, 403):
                DOWNLOAD_STATUS[tracker_name] = "ERROR · Authentication required or API key rejected"
            else:
                DOWNLOAD_STATUS[tracker_name] = f"ERROR · API HTTP {response.status_code}"
            FAILED_IDS.add(model_id)
            return

        model_data = response.json()
        versions = model_data.get("modelVersions") or []
        if not versions:
            DOWNLOAD_STATUS[tracker_name] = "ERROR · No downloadable model versions found"
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
            DOWNLOAD_STATUS[tracker_name] = "ERROR · No .safetensors model file found"
            FAILED_IDS.add(model_id)
            return

        download_url = primary_file.get("downloadUrl") or (
            f"{CIVITAI_BASE_URL}/api/download/models/{version['id']}"
        )
    except (requests.RequestException, ValueError, KeyError) as exc:
        DOWNLOAD_STATUS[tracker_name] = f"ERROR · {str(exc)[:80]}"
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
        DOWNLOAD_STATUS[tracker_name] = "DONE · Already exists"
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
                    DOWNLOAD_STATUS[tracker_name] = "ERROR · Download requires a valid Civitai API key"
                else:
                    DOWNLOAD_STATUS[tracker_name] = f"ERROR · HTTP {download_response.status_code}"
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
                        DOWNLOAD_STATUS[tracker_name] = f"{progress:5.1f}% · {speed:.1f} MB/s"
                    else:
                        downloaded_mb = downloaded_bytes / (1024 * 1024)
                        DOWNLOAD_STATUS[tracker_name] = f"{downloaded_mb:.1f} MB · {speed:.1f} MB/s"

        os.replace(partial_path, safetensors_path)
        DOWNLOAD_STATUS[tracker_name] = "DONE · Complete"
        FAILED_IDS.discard(model_id)
    except (requests.RequestException, OSError, ValueError) as exc:
        try:
            if os.path.exists(partial_path):
                os.remove(partial_path)
        except OSError:
            pass
        DOWNLOAD_STATUS[tracker_name] = f"ERROR · {str(exc)[:80]}"
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
        is_error = status.startswith("ERROR")
        ttl = 60 if is_error else 8

        if status.startswith("DONE") or is_error:
            if name not in EXPIRATION_REGISTRY:
                EXPIRATION_REGISTRY[name] = now
            elif now - EXPIRATION_REGISTRY[name] > ttl:
                DOWNLOAD_STATUS.pop(name, None)
                EXPIRATION_REGISTRY.pop(name, None)

    if ACTIVE_TASKS > 0 or DOWNLOAD_STATUS:
        log_out = []
        if ACTIVE_TASKS > 0:
            log_out.append(f"ACTIVE DOWNLOADS  {ACTIVE_TASKS}\n" + "─" * 34)
        log_out.extend(
            [f"{name[:36]}\n  {status}\n" for name, status in DOWNLOAD_STATUS.items()]
        )
        return text_update, "\n".join(log_out)

    return text_update, "IDLE\nCopy a Civitai model link to start."


def retry_failed(threads):
    if not FAILED_IDS:
        return "No failed downloads to retry."

    to_retry = list(FAILED_IDS)
    queued = start_downloads(to_retry, threads, force=True)
    return f"Retrying {queued} failed download(s)."


def reset_all():
    global LAST_CLIPBOARD
    with TASK_LOCK:
        DOWNLOAD_STATUS.clear()
        PROCESSED_IDS.clear()
        EXPIRATION_REGISTRY.clear()
        FAILED_IDS.clear()
        LAST_CLIPBOARD = ""
    return "", "IDLE\nActivity cleared."


def open_loras():
    os.makedirs(LORA_DIR, exist_ok=True)
    try:
        os.startfile(LORA_DIR)
        return f"Opened LoRA directory: `{LORA_DIR}`"
    except OSError as exc:
        return f"Could not open LoRA directory: `{html.escape(str(exc)[:120])}`"


def open_civitai():
    try:
        opened = webbrowser.open_new_tab(CIVITAI_BASE_URL)
        if opened:
            return "Opened Civitai in your normal browser. Use this for Google/Civitai website login."
        return "Your browser did not acknowledge the request. Open https://civitai.com manually."
    except Exception as exc:
        return f"Could not open browser: `{html.escape(str(exc)[:120])}`"


def open_api_key_settings():
    try:
        opened = webbrowser.open_new_tab(CIVITAI_SETTINGS_URL)
        if opened:
            return (
                "Opened Civitai Settings. Sign in if needed, create an API key, "
                "copy it, then paste it into the API Access card."
            )
        return f"Open {CIVITAI_SETTINGS_URL} manually."
    except Exception as exc:
        return f"Could not open Civitai Settings: `{html.escape(str(exc)[:120])}`"


def build_civitai_frame(cache_buster=None):
    suffix = f"?cf_reload={cache_buster}" if cache_buster else ""
    return (
        f'<div class="cf-frame-shell"><iframe src="{CIVITAI_BASE_URL}/{suffix}" '
        'title="Civitai embedded browser" '
        'referrerpolicy="strict-origin-when-cross-origin" '
        'allow="clipboard-read; clipboard-write; fullscreen" '
        'loading="eager"></iframe></div>'
    )


def reload_civitai_frame():
    return build_civitai_frame(int(time.time()))


def brand_html():
    return """
    <div class="cf-brand">
        <div class="cf-brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
                <path d="M7.2 3.8h9.6l4.8 8.2-4.8 8.2H7.2L2.4 12l4.8-8.2Z" stroke="currentColor" stroke-width="1.7"/>
                <path d="M8.4 8.2h7.2l2.2 3.8-2.2 3.8H8.4L6.2 12l2.2-3.8Z" stroke="currentColor" stroke-width="1.7"/>
                <circle cx="12" cy="12" r="1.6" fill="currentColor"/>
            </svg>
        </div>
        <div>
            <div class="cf-brand-row">
                <span class="cf-brand-name">CivitaiFlow</span>
                <span class="cf-version">v22.4</span>
            </div>
            <div class="cf-brand-sub">Embedded Civitai · API-powered downloads · Forge native</div>
        </div>
    </div>
    """


def connection_help_html():
    return """
    <div class="cf-help">
        <strong>API auth is not a second website login.</strong>
        It gives CivitaiFlow a token for authenticated metadata and gated downloads.
        The embedded Civitai page keeps its own browser session.
        <ol>
            <li>Open <b>Get API Key</b> and sign in to Civitai normally.</li>
            <li>Create/copy an API key in Civitai Settings.</li>
            <li>Paste it here and click <b>Connect API</b>.</li>
        </ol>
    </div>
    """


def on_ui_tabs():
    custom_css = """
    #cf_root {
        --cf-border: rgba(148, 163, 184, 0.18);
        --cf-border-strong: rgba(148, 163, 184, 0.28);
        --cf-panel: rgba(15, 23, 42, 0.42);
        --cf-panel-strong: rgba(15, 23, 42, 0.72);
        --cf-text-dim: #94a3b8;
        --cf-accent: #f97316;
        --cf-ok: #34d399;
        --cf-warn: #fbbf24;
        --cf-error: #fb7185;
        gap: 14px;
    }
    #cf_root .gradio-row {
        gap: 14px;
    }
    .cf-brand {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 2px 2px 10px;
    }
    .cf-brand-mark {
        width: 34px;
        height: 34px;
        display: grid;
        place-items: center;
        color: var(--cf-accent);
    }
    .cf-brand-mark svg {
        width: 30px;
        height: 30px;
    }
    .cf-brand-row {
        display: flex;
        align-items: center;
        gap: 9px;
        line-height: 1;
    }
    .cf-brand-name {
        font-size: 21px;
        font-weight: 750;
        letter-spacing: -0.025em;
    }
    .cf-version {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: .04em;
        padding: 4px 7px;
        border: 1px solid var(--cf-border-strong);
        border-radius: 999px;
        color: var(--cf-text-dim);
    }
    .cf-brand-sub {
        margin-top: 6px;
        color: var(--cf-text-dim);
        font-size: 12px;
    }
    #cf_connection_card,
    #cf_capture_card,
    #cf_activity_card {
        border: 1px solid var(--cf-border) !important;
        border-radius: 14px !important;
        background: var(--cf-panel) !important;
        padding: 13px !important;
        box-shadow: none !important;
    }
    .cf-section-label {
        margin: 0 0 10px;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: .12em;
        font-weight: 750;
        color: var(--cf-text-dim);
    }
    .cf-status {
        display: flex;
        align-items: center;
        gap: 9px;
        min-height: 42px;
        border: 1px solid var(--cf-border);
        border-radius: 10px;
        padding: 9px 11px;
        margin-bottom: 9px;
        background: rgba(2, 6, 23, .24);
    }
    .cf-status-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        flex: 0 0 auto;
        background: var(--cf-text-dim);
        box-shadow: 0 0 0 4px rgba(148, 163, 184, .08);
    }
    .cf-status-ok .cf-status-dot {
        background: var(--cf-ok);
        box-shadow: 0 0 0 4px rgba(52, 211, 153, .1);
    }
    .cf-status-warn .cf-status-dot {
        background: var(--cf-warn);
        box-shadow: 0 0 0 4px rgba(251, 191, 36, .1);
    }
    .cf-status-error .cf-status-dot {
        background: var(--cf-error);
        box-shadow: 0 0 0 4px rgba(251, 113, 133, .1);
    }
    .cf-status-copy {
        display: flex;
        flex-direction: column;
        line-height: 1.25;
        min-width: 0;
    }
    .cf-status-copy strong {
        font-size: 12px;
    }
    .cf-status-detail {
        margin-top: 3px;
        color: var(--cf-text-dim);
        font-size: 11px;
        white-space: normal;
    }
    .cf-help {
        color: var(--cf-text-dim);
        font-size: 12px;
        line-height: 1.5;
        padding: 4px 2px;
    }
    .cf-help strong {
        color: inherit;
    }
    .cf-help ol {
        margin: 8px 0 0 18px;
        padding: 0;
    }
    #cf_api_key textarea,
    #cf_api_key input {
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
        letter-spacing: .04em;
    }
    #cf_btn_connect {
        border-color: rgba(249, 115, 22, .35) !important;
    }
    #cf_terminal textarea {
        background: rgba(2, 6, 23, .72) !important;
        color: #cbd5e1 !important;
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
        font-size: 12px !important;
        line-height: 1.55 !important;
        border-radius: 10px !important;
        border: 1px solid var(--cf-border) !important;
        box-shadow: none !important;
    }
    #cf_dropzone textarea {
        background: rgba(2, 6, 23, .28) !important;
        border: 1px dashed var(--cf-border-strong) !important;
        border-radius: 10px !important;
        text-align: left;
    }
    #cf_root button {
        border-radius: 9px !important;
        font-weight: 650 !important;
        min-height: 38px;
    }
    #cf_root button.primary {
        box-shadow: none !important;
    }
    .cf-frame-shell {
        height: 92vh;
        min-height: 720px;
        overflow: hidden;
        border: 1px solid var(--cf-border);
        border-radius: 14px;
        background: #0b0f19;
        box-shadow: 0 12px 30px rgba(0, 0, 0, .16);
    }
    .cf-frame-shell iframe {
        display: block;
        width: 100%;
        height: 100%;
        border: 0;
        background: #0b0f19;
    }
    #cf_action_status {
        min-height: 18px;
        color: var(--cf-text-dim);
        font-size: 12px;
    }
    """

    with gr.Blocks(analytics_enabled=False, css=custom_css, elem_id="cf_root") as cf_tab:
        timer = gr.Timer(1.5)

        with gr.Row():
            with gr.Column(scale=2, min_width=320):
                gr.HTML(brand_html())

                with gr.Group(elem_id="cf_connection_card"):
                    gr.HTML('<div class="cf-section-label">Civitai connection</div>')
                    api_status = gr.HTML(initial_api_status())

                    api_key_input = gr.Textbox(
                        label="API key",
                        placeholder="Paste your Civitai API key",
                        type="password",
                        elem_id="cf_api_key",
                    )

                    with gr.Row():
                        btn_connect_api = gr.Button(
                            "Connect API",
                            variant="primary",
                            elem_id="cf_btn_connect",
                        )
                        btn_check_api = gr.Button("Verify", variant="secondary")

                    with gr.Row():
                        btn_get_api_key = gr.Button("Get API Key ↗", variant="secondary")
                        btn_disconnect_api = gr.Button("Disconnect", variant="secondary")

                    with gr.Accordion("How API authentication works", open=False):
                        gr.HTML(connection_help_html())

                with gr.Group(elem_id="cf_capture_card"):
                    gr.HTML('<div class="cf-section-label">Capture & download</div>')

                    with gr.Row(variant="panel"):
                        sniper = gr.Checkbox(label="Sniper capture", value=True)
                        auto = gr.Checkbox(label="Auto download", value=True)

                    url_box = gr.Textbox(
                        label="Model links",
                        lines=2,
                        placeholder="Copy or paste civitai.com/models/... links",
                        elem_id="cf_dropzone",
                        show_label=False,
                    )

                    with gr.Row():
                        btn_folder = gr.Button("Open LoRA Folder", variant="secondary")
                        btn_reload_frame = gr.Button("Reload Panel", variant="secondary")

                    with gr.Accordion("Advanced", open=False):
                        th_slider = gr.Slider(
                            1,
                            10,
                            5,
                            step=1,
                            label="Concurrent downloads",
                        )
                        btn_open_civitai = gr.Button(
                            "Open Civitai in Browser ↗",
                            variant="secondary",
                        )

                with gr.Group(elem_id="cf_activity_card"):
                    gr.HTML('<div class="cf-section-label">Activity</div>')
                    with gr.Row():
                        btn_retry = gr.Button("Retry failed", variant="primary")
                        btn_clear = gr.Button("Clear", variant="secondary")

                    log_box = gr.Textbox(
                        label="",
                        show_label=False,
                        lines=15,
                        value="IDLE\nCopy a Civitai model link to start.",
                        interactive=False,
                        elem_id="cf_terminal",
                    )

                action_status = gr.Markdown(elem_id="cf_action_status")

            with gr.Column(scale=7, min_width=640):
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
        btn_get_api_key.click(fn=open_api_key_settings, outputs=[action_status])
        btn_check_api.click(fn=check_api_status, outputs=[api_status])
        btn_connect_api.click(
            fn=save_and_connect_api,
            inputs=[api_key_input],
            outputs=[api_status, api_key_input],
        )
        api_key_input.submit(
            fn=save_and_connect_api,
            inputs=[api_key_input],
            outputs=[api_status, api_key_input],
        )
        btn_disconnect_api.click(
            fn=disconnect_api,
            outputs=[api_status, api_key_input],
        )
        btn_reload_frame.click(fn=reload_civitai_frame, outputs=[civitai_frame])

    return [(cf_tab, "CivitaiFlow", "cf_tab")]


script_callbacks.on_ui_tabs(on_ui_tabs)
