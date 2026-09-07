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
from urllib.parse import parse_qs, urlparse

LORA_DIR = os.path.join(paths.models_path, "Lora")
CIVITAI_BASE_URL = "https://civitai.com"
CIVITAI_API_URL = f"{CIVITAI_BASE_URL}/api/v1"
CIVITAI_SETTINGS_URL = f"{CIVITAI_BASE_URL}/user/account"
CIVITAIFLOW_VERSION = "22.8.0-rc1"

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
            {"visible": True, "type": "password"},
            section=section,
        ),
    )


script_callbacks.on_ui_settings(on_ui_settings)


def get_api_key():
    return str(shared.opts.data.get("civitai_api_key", "") or "").strip()


def build_headers(api_key=None):
    api_key = (api_key if api_key is not None else get_api_key()).strip()
    headers = {"User-Agent": f"CivitaiFlow/{CIVITAIFLOW_VERSION} (Stable Diffusion Forge)"}
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
            f"{mask_key(api_key)} · Click Verify if you want to re-check access.",
        )
    return status_html(
        "muted",
        "API access not configured",
        "Public models still work. Private or gated downloads need a Civitai API key.",
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
            "Paste a key in Connection settings, then click Connect API.",
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
            "Public downloads remain available; gated downloads will require a key.",
        ),
        gr.update(value=""),
    )


def get_windows_clipboard():
    """Read clipboard text in an isolated process.

    Do not replace this with direct ctypes/Win32 memory access: an earlier CivitaiFlow
    release explicitly moved away from that path after Forge memory-segfault reports.
    """
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
        if len(text) > 4096 or "$uiCode" in text or "import os" in text:
            return ""
        return text
    except Exception:
        return ""


def _target_token(model_id=None, version_id=None):
    model_id = str(model_id or "").strip()
    version_id = str(version_id or "").strip()
    if model_id.isdigit() and version_id.isdigit():
        return f"model:{model_id}:version:{version_id}"
    if model_id.isdigit():
        return f"model:{model_id}"
    if version_id.isdigit():
        return f"version:{version_id}"
    return None


def _decode_target_token(value):
    value = str(value or "").strip()
    match = re.fullmatch(r"model:(\d+):version:(\d+)", value)
    if match:
        return {"model_id": match.group(1), "version_id": match.group(2)}
    match = re.fullmatch(r"model:(\d+)", value)
    if match:
        return {"model_id": match.group(1), "version_id": None}
    match = re.fullmatch(r"version:(\d+)", value)
    if match:
        return {"model_id": None, "version_id": match.group(1)}
    if value.isdigit():
        return {"model_id": value, "version_id": None}
    return None


def parse_civitai_urls(text):
    """Parse model-page links and copied Civitai file-download links.

    Civitai's `/models/<id>` path contains a model ID. In contrast,
    `/api/download/models/<id>` contains a model *version* ID. Treating both as
    model IDs was the reason copied file links silently failed in older builds.
    """
    text = str(text or "")
    results = []
    seen = set()

    url_candidates = re.findall(r"https?://(?:www\.)?civitai\.com/[^\s<>'\"]+", text, flags=re.I)
    for raw in url_candidates:
        try:
            parsed = urlparse(raw)
        except ValueError:
            continue

        page_match = re.match(r"^/models/(\d+)(?:/|$)", parsed.path, flags=re.I)
        if page_match:
            version_id = (parse_qs(parsed.query).get("modelVersionId") or [None])[0]
            token = _target_token(page_match.group(1), version_id)
        else:
            download_match = re.match(r"^/api/download/models/(\d+)(?:/|$)", parsed.path, flags=re.I)
            token = _target_token(version_id=download_match.group(1)) if download_match else None

        if token and token not in seen:
            seen.add(token)
            results.append(token)

    for number in re.findall(r"^\s*(\d+)\s*$", text, flags=re.MULTILINE):
        token = _target_token(model_id=number)
        if token and token not in seen:
            seen.add(token)
            results.append(token)

    return results


def safe_filename_component(value, fallback="General"):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "")).strip(" .")
    return value[:120] or fallback


def strip_html(value):
    return re.sub(r"<[^>]+>", "", value or "").strip()


def _resolve_model_and_version(target, headers):
    parsed_target = _decode_target_token(target)
    if not parsed_target:
        raise RuntimeError("Unrecognized Civitai target")

    model_id = parsed_target.get("model_id")
    requested_version_id = parsed_target.get("version_id")

    if not model_id and requested_version_id:
        version_response = requests.get(
            f"{CIVITAI_API_URL}/model-versions/{requested_version_id}",
            headers=headers,
            timeout=20,
        )
        if version_response.status_code != 200:
            raise RuntimeError(f"Civitai version API returned HTTP {version_response.status_code}")
        version_payload = version_response.json()
        model_id = str(
            version_payload.get("modelId")
            or (version_payload.get("model") or {}).get("id")
            or ""
        ).strip()
        if not model_id.isdigit():
            raise RuntimeError("Civitai version response did not include a model ID")

    model_response = requests.get(
        f"{CIVITAI_API_URL}/models/{model_id}",
        headers=headers,
        timeout=20,
    )
    if model_response.status_code != 200:
        if model_response.status_code in (401, 403):
            raise PermissionError("Authentication required or API key rejected")
        raise RuntimeError(f"Civitai model API returned HTTP {model_response.status_code}")

    model_data = model_response.json()
    versions = model_data.get("modelVersions") or []
    if not versions:
        raise RuntimeError("No downloadable model versions found")

    if requested_version_id:
        version = next(
            (item for item in versions if str(item.get("id")) == str(requested_version_id)),
            None,
        )
        if not version:
            raise RuntimeError(f"Requested model version {requested_version_id} was not found")
    else:
        version = versions[0]

    return model_data, version


def download_by_id(target, api_key):
    global DOWNLOAD_STATUS, FAILED_IDS

    parsed_target = _decode_target_token(target)
    tracker_key = str(target)
    tracker_name = (
        f"Version {parsed_target['version_id']}"
        if parsed_target and not parsed_target.get("model_id")
        else f"Model {parsed_target.get('model_id') if parsed_target else target}"
    )
    DOWNLOAD_STATUS[tracker_name] = "Connecting..."
    headers = build_headers(api_key)

    try:
        model_data, version = _resolve_model_and_version(target, headers)
        model_id = str(model_data.get("id") or (parsed_target or {}).get("model_id") or "")

        files_list = version.get("files") or []
        candidates = [
            file_info
            for file_info in files_list
            if file_info.get("type") == "Model"
            and str(file_info.get("name", "")).lower().endswith((".safetensors", ".ckpt"))
        ]
        if not candidates:
            candidates = [
                file_info
                for file_info in files_list
                if str(file_info.get("name", "")).lower().endswith((".safetensors", ".ckpt"))
            ]
        primary_file = next((item for item in candidates if item.get("primary") is True), None)
        primary_file = primary_file or (candidates[0] if candidates else None)
        if not primary_file:
            raise RuntimeError("No supported model file found")

        download_url = primary_file.get("downloadUrl") or (
            f"{CIVITAI_BASE_URL}/api/download/models/{version['id']}"
        )
    except PermissionError as exc:
        DOWNLOAD_STATUS[tracker_name] = f"ERROR · {str(exc)}"
        FAILED_IDS.add(tracker_key)
        return
    except (requests.RequestException, ValueError, KeyError, RuntimeError) as exc:
        DOWNLOAD_STATUS[tracker_name] = f"ERROR · {str(exc)[:120]}"
        FAILED_IDS.add(tracker_key)
        return

    clean_name = safe_filename_component(model_data.get("name"), tracker_name)
    DOWNLOAD_STATUS.pop(tracker_name, None)
    tracker_name = clean_name

    model_type = str(model_data.get("type") or "LORA")
    if model_type == "Checkpoint":
        target_dir = os.path.join(paths.models_path, "Stable-diffusion")
    elif model_type == "VAE":
        target_dir = os.path.join(paths.models_path, "VAE")
    else:
        tag = (model_data.get("tags") or ["General"])[0]
        target_dir = os.path.join(LORA_DIR, safe_filename_component(tag))
    os.makedirs(target_dir, exist_ok=True)

    source_name = safe_filename_component(primary_file.get("name"), f"{clean_name}.safetensors")
    extension = os.path.splitext(source_name)[1].lower()
    if extension not in {".safetensors", ".ckpt"}:
        extension = ".safetensors"
    version_suffix = str(version.get("id") or "")
    base_name = clean_name
    destination = os.path.join(target_dir, f"{base_name}{extension}")

    # Never overwrite a different version blindly. Keep the familiar clean name
    # for first installs; use the version ID only when that name already exists.
    if os.path.exists(destination):
        sidecar = os.path.splitext(destination)[0] + ".json"
        installed_version = None
        try:
            with open(sidecar, "r", encoding="utf-8") as handle:
                installed_version = str((json.load(handle) or {}).get("civitai version id") or "")
        except (OSError, ValueError, TypeError):
            installed_version = None

        if installed_version and installed_version == version_suffix:
            DOWNLOAD_STATUS[tracker_name] = "DONE · Already installed"
            FAILED_IDS.discard(tracker_key)
            return
        destination = os.path.join(target_dir, f"{base_name}__v{version_suffix}{extension}")
        if os.path.exists(destination):
            DOWNLOAD_STATUS[tracker_name] = "DONE · Version already exists"
            FAILED_IDS.discard(tracker_key)
            return

    partial_path = f"{destination}.part"
    metadata_base = os.path.splitext(destination)[0]

    try:
        forge_json = {
            "description": strip_html(model_data.get("description", "")),
            "sd version": version.get("baseModel", "Unknown"),
            "activation text": ", ".join(version.get("trainedWords", [])),
            "preferred weight": 1.0,
            "civitai model id": model_data.get("id"),
            "civitai version id": version.get("id"),
            "civitai file name": primary_file.get("name"),
        }
        with open(f"{metadata_base}.json", "w", encoding="utf-8") as file_handle:
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
                        with open(f"{metadata_base}.png", "wb") as file_handle:
                            file_handle.write(image_response.content)
            except (requests.RequestException, OSError, KeyError):
                pass

        with requests.get(
            download_url,
            headers=headers,
            stream=True,
            timeout=600,
        ) as download_response:
            if download_response.status_code not in (200, 206):
                if download_response.status_code in (401, 403):
                    DOWNLOAD_STATUS[tracker_name] = "ERROR · Download requires a valid Civitai API key"
                else:
                    DOWNLOAD_STATUS[tracker_name] = f"ERROR · HTTP {download_response.status_code}"
                FAILED_IDS.add(tracker_key)
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

        os.replace(partial_path, destination)
        DOWNLOAD_STATUS[tracker_name] = "DONE · Complete"
        FAILED_IDS.discard(tracker_key)
    except (requests.RequestException, OSError, ValueError) as exc:
        try:
            if os.path.exists(partial_path):
                os.remove(partial_path)
        except OSError:
            pass
        DOWNLOAD_STATUS[tracker_name] = f"ERROR · {str(exc)[:100]}"
        FAILED_IDS.add(tracker_key)


def _download_worker(target, api_key):
    global ACTIVE_TASKS
    try:
        download_by_id(target, api_key)
    finally:
        with TASK_LOCK:
            ACTIVE_TASKS = max(0, ACTIVE_TASKS - 1)


def start_downloads(targets, threads, force=False):
    global ACTIVE_TASKS, PROCESSED_IDS

    normalized = [str(target).strip() for target in targets if _decode_target_token(target)]
    if not normalized:
        return 0

    max_workers = max(1, min(int(threads), 10))
    api_key = get_api_key()

    with TASK_LOCK:
        accepted = []
        for target in normalized:
            if force or target not in PROCESSED_IDS:
                PROCESSED_IDS.add(target)
                accepted.append(target)
        ACTIVE_TASKS += len(accepted)

    if not accepted:
        return 0

    def run_pool(items):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_download_worker, target, api_key) for target in items]
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
        targets = parse_civitai_urls(clip)
        if clip and targets and clip != LAST_CLIPBOARD:
            LAST_CLIPBOARD = clip
            if is_auto:
                queued = start_downloads(targets, threads)
                if queued:
                    current_text = ""
                    text_update = ""
            elif clip not in current_text:
                current_text = (
                    current_text.strip() + "\n" + clip
                    if current_text.strip()
                    else clip
                )
                text_update = current_text

    if is_auto and current_text.strip():
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
            [f"{name[:42]}\n  {status}\n" for name, status in DOWNLOAD_STATUS.items()]
        )
        return text_update, "\n".join(log_out)

    return text_update, "IDLE\nCopy or paste a Civitai model/file link."


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


def send_now(text, threads):
    targets = parse_civitai_urls(text)
    if not targets:
        return gr.update(), "No valid Civitai model or file link found."
    queued = start_downloads(targets, threads)
    if queued:
        return "", f"Queued {queued} download(s)."
    return gr.update(), "Nothing queued: target may already be active/processed."


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
            return "Opened Civitai in your normal browser. Use this for website login and browsing."
        return "Your browser did not acknowledge the request. Open https://civitai.com manually."
    except Exception as exc:
        return f"Could not open browser: `{html.escape(str(exc)[:120])}`"


def open_api_key_settings():
    try:
        opened = webbrowser.open_new_tab(CIVITAI_SETTINGS_URL)
        if opened:
            return "Opened your Civitai account page. Create/copy an API key, then paste it into Connection settings."
        return f"Open {CIVITAI_SETTINGS_URL} manually."
    except Exception as exc:
        return f"Could not open Civitai account: `{html.escape(str(exc)[:120])}`"


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
    return f"""
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
                <span class="cf-version">v{CIVITAIFLOW_VERSION}</span>
            </div>
            <div class="cf-brand-sub">Stable core · Civitai acquisition for Forge</div>
        </div>
    </div>
    """


def connection_help_html():
    return """
    <div class="cf-help">
        <strong>API key = download access, not website login.</strong>
        Website login stays in your normal Civitai browser session. The API key is used only for metadata and gated downloads.
    </div>
    """


def on_ui_tabs():
    custom_css = """
    #cf_root {
        --cf-border: rgba(148, 163, 184, 0.18);
        --cf-border-strong: rgba(148, 163, 184, 0.28);
        --cf-panel: rgba(15, 23, 42, 0.42);
        --cf-text-dim: #94a3b8;
        --cf-accent: #f97316;
        --cf-ok: #34d399;
        --cf-warn: #fbbf24;
        --cf-error: #fb7185;
        gap: 12px;
    }
    #cf_root .gradio-row { gap: 12px; }
    .cf-brand { display:flex; align-items:center; gap:10px; padding:2px 2px 8px; }
    .cf-brand-mark { width:32px; height:32px; flex:0 0 32px; display:grid; place-items:center; color:var(--cf-accent); }
    .cf-brand-mark svg { width:27px; height:27px; }
    .cf-brand-row { display:flex; align-items:center; gap:8px; line-height:1; }
    .cf-brand-name { font-size:20px; font-weight:750; letter-spacing:-.025em; }
    .cf-version { font-size:10px; font-weight:700; padding:3px 6px; border:1px solid var(--cf-border-strong); border-radius:999px; color:var(--cf-text-dim); }
    .cf-brand-sub { margin-top:5px; color:var(--cf-text-dim); font-size:11px; }
    #cf_connection_card, #cf_capture_card, #cf_activity_card {
        border:1px solid var(--cf-border) !important;
        border-radius:12px !important;
        background:var(--cf-panel) !important;
        padding:11px !important;
        box-shadow:none !important;
    }
    .cf-section-label { margin:0 0 8px; font-size:10px; text-transform:uppercase; letter-spacing:.12em; font-weight:750; color:var(--cf-text-dim); }
    .cf-status { display:flex; align-items:center; gap:8px; min-height:38px; border:1px solid var(--cf-border); border-radius:9px; padding:8px 9px; margin-bottom:7px; background:rgba(2,6,23,.24); }
    .cf-status-dot { width:7px; height:7px; border-radius:999px; flex:0 0 auto; background:var(--cf-text-dim); }
    .cf-status-ok .cf-status-dot { background:var(--cf-ok); }
    .cf-status-warn .cf-status-dot { background:var(--cf-warn); }
    .cf-status-error .cf-status-dot { background:var(--cf-error); }
    .cf-status-copy { display:flex; flex-direction:column; line-height:1.2; min-width:0; }
    .cf-status-copy strong { font-size:11px; }
    .cf-status-detail { margin-top:2px; color:var(--cf-text-dim); font-size:10px; white-space:normal; }
    .cf-help { color:var(--cf-text-dim); font-size:11px; line-height:1.45; padding:3px 1px; }
    #cf_api_key textarea, #cf_api_key input { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace !important; letter-spacing:.03em; }
    #cf_btn_connect { border-color:rgba(249,115,22,.35) !important; }
    #cf_terminal textarea { min-height:125px !important; background:rgba(2,6,23,.72) !important; color:#cbd5e1 !important; font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace !important; font-size:11px !important; line-height:1.45 !important; border-radius:9px !important; border:1px solid var(--cf-border) !important; box-shadow:none !important; }
    #cf_dropzone textarea { background:rgba(2,6,23,.28) !important; border:1px dashed var(--cf-border-strong) !important; border-radius:9px !important; text-align:left; }
    #cf_root button { border-radius:8px !important; font-weight:650 !important; min-height:34px; }
    #cf_root button.primary { box-shadow:none !important; }
    .cf-frame-shell { height:86vh; min-height:650px; overflow:hidden; border:1px solid var(--cf-border); border-radius:12px; background:#0b0f19; box-shadow:0 12px 30px rgba(0,0,0,.16); }
    .cf-frame-shell iframe { display:block; width:100%; height:100%; border:0; background:#0b0f19; }
    #cf_action_status { min-height:16px; color:var(--cf-text-dim); font-size:11px; }
    """

    with gr.Blocks(analytics_enabled=False, css=custom_css, elem_id="cf_root") as cf_tab:
        timer = gr.Timer(2.0)

        with gr.Row():
            with gr.Column(scale=2, min_width=330):
                gr.HTML(brand_html())

                with gr.Group(elem_id="cf_connection_card"):
                    gr.HTML('<div class="cf-section-label">Connection</div>')
                    api_status = gr.HTML(initial_api_status())
                    with gr.Accordion("Connection settings", open=False):
                        api_key_input = gr.Textbox(
                            label="API key",
                            placeholder="Paste your Civitai API key",
                            type="password",
                            elem_id="cf_api_key",
                        )
                        with gr.Row():
                            btn_connect_api = gr.Button("Connect API", variant="primary", elem_id="cf_btn_connect")
                            btn_check_api = gr.Button("Verify", variant="secondary")
                        with gr.Row():
                            btn_get_api_key = gr.Button("Get API Key ↗", variant="secondary")
                            btn_disconnect_api = gr.Button("Disconnect", variant="secondary")
                        gr.HTML(connection_help_html())

                with gr.Group(elem_id="cf_capture_card"):
                    gr.HTML('<div class="cf-section-label">Capture & download</div>')
                    url_box = gr.Textbox(
                        label="Model or file links",
                        lines=2,
                        placeholder="Paste /models/... or /api/download/models/... links",
                        elem_id="cf_dropzone",
                        show_label=False,
                    )
                    btn_send = gr.Button("Send now", variant="primary")
                    with gr.Row(variant="panel"):
                        sniper = gr.Checkbox(label="Sniper capture", value=True)
                        auto = gr.Checkbox(label="Auto download", value=True)
                    with gr.Row():
                        btn_folder = gr.Button("Open model folder", variant="secondary")
                        btn_reload_frame = gr.Button("Reload Civitai", variant="secondary")
                    with gr.Accordion("Advanced", open=False):
                        th_slider = gr.Slider(1, 10, 5, step=1, label="Concurrent downloads")
                        btn_open_civitai = gr.Button("Open Civitai in Browser ↗", variant="secondary")

                with gr.Group(elem_id="cf_activity_card"):
                    gr.HTML('<div class="cf-section-label">Activity</div>')
                    with gr.Row():
                        btn_retry = gr.Button("Retry failed", variant="secondary")
                        btn_clear = gr.Button("Clear", variant="secondary")
                    log_box = gr.Textbox(
                        label="",
                        show_label=False,
                        lines=8,
                        value="IDLE\nCopy or paste a Civitai model/file link.",
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
        btn_send.click(fn=send_now, inputs=[url_box, th_slider], outputs=[url_box, action_status])
        url_box.submit(fn=send_now, inputs=[url_box, th_slider], outputs=[url_box, action_status])
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
        btn_disconnect_api.click(fn=disconnect_api, outputs=[api_status, api_key_input])
        btn_reload_frame.click(fn=reload_civitai_frame, outputs=[civitai_frame])

    return [(cf_tab, "CivitaiFlow", "cf_tab")]


script_callbacks.on_ui_tabs(on_ui_tabs)
