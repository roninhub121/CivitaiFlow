import json
import os
import re
import shutil
import threading
import time

import gradio as gr
import requests
from fastapi import Body, FastAPI, Request
from modules import script_callbacks, script_loading, shared


SCHEMA = 1
STATE_LOCK = threading.RLock()
RESUME_LOCK = threading.RLock()
RESUME_STARTED = False
QUEUE_LAST_FLUSH = {}
ORIGINAL_ELIGIBLE_FOR_AUTO = None
ORIGINAL_UPDATE_SUMMARY = None


def _find_module(filename):
    filename = filename.lower()
    for script_path, module in script_loading.loaded_scripts.items():
        if os.path.basename(script_path).lower() == filename:
            return module
    return None


LIB = _find_module("zz_civitaiflow_library.py")
UPD = _find_module("zzz_civitaiflow_updates.py")
DATA_DIR = LIB.DATA_DIR if LIB else None
LIFECYCLE_FILE = os.path.join(DATA_DIR, "lifecycle-state.json") if DATA_DIR else None
QUEUE_FILE = os.path.join(DATA_DIR, "download-queue.json") if DATA_DIR else None
HISTORY_FILE = os.path.join(DATA_DIR, "history.jsonl") if DATA_DIR else None
LIFECYCLE_STATE = {"schema": SCHEMA, "policies": {}}
QUEUE_STATE = {"schema": SCHEMA, "items": {}, "updated_at": None}


def on_ui_settings():
    section = ("civitai_flow", "CivitaiFlow Manager")
    shared.opts.add_option(
        "civitai_resume_downloads_on_startup",
        shared.OptionInfo(True, "Resume interrupted CivitaiFlow downloads after Forge starts", section=section),
    )
    shared.opts.add_option(
        "civitai_min_free_space_gb",
        shared.OptionInfo(5, "Minimum free disk space to keep after a CivitaiFlow download (GB)", gr.Number, {"precision": 1}, section=section),
    )
    shared.opts.add_option(
        "civitai_auto_refresh_forge_models",
        shared.OptionInfo(True, "Refresh Forge model inventories after CivitaiFlow installs an asset", section=section),
    )
    shared.opts.add_option(
        "civitai_history_limit",
        shared.OptionInfo(500, "Maximum CivitaiFlow lifecycle history entries returned by the local API", gr.Number, {"precision": 0}, section=section),
    )


script_callbacks.on_ui_settings(on_ui_settings)


def _option(name, default):
    try:
        return getattr(shared.opts, name)
    except Exception:
        return shared.opts.data.get(name, default)


def _atomic_json(path, payload):
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    os.replace(temp_path, path)


def _save_lifecycle():
    with STATE_LOCK:
        payload = {"schema": SCHEMA, "policies": LIFECYCLE_STATE.get("policies", {})}
    _atomic_json(LIFECYCLE_FILE, payload)


def _save_queue(force=False, key=None):
    now = time.time()
    if not force and key:
        if now - QUEUE_LAST_FLUSH.get(key, 0) < 1.5:
            return
        QUEUE_LAST_FLUSH[key] = now
    with STATE_LOCK:
        QUEUE_STATE["updated_at"] = now
        payload = {"schema": SCHEMA, "items": QUEUE_STATE.get("items", {}), "updated_at": now}
    _atomic_json(QUEUE_FILE, payload)


def _load_state():
    if LIFECYCLE_FILE:
        try:
            with open(LIFECYCLE_FILE, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("schema") == SCHEMA and isinstance(payload.get("policies"), dict):
                LIFECYCLE_STATE["policies"] = payload["policies"]
        except (OSError, ValueError, TypeError):
            pass
    if QUEUE_FILE:
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("schema") == SCHEMA and isinstance(payload.get("items"), dict):
                QUEUE_STATE["items"] = payload["items"]
                QUEUE_STATE["updated_at"] = payload.get("updated_at")
        except (OSError, ValueError, TypeError):
            pass
    changed = False
    with STATE_LOCK:
        for item in QUEUE_STATE["items"].values():
            if item.get("state") in {"queued", "resolving", "downloading", "verifying"}:
                item["state"] = "interrupted"
                item["message"] = "Interrupted by Forge shutdown; eligible for resume"
                changed = True
    if changed:
        _save_queue(force=True)


def _queue_key(target):
    target = LIB.parse_target(target) if LIB else None
    return LIB._target_key(target) if target else None


def _queue_update(target, force_save=False, **values):
    key = _queue_key(target)
    if not key:
        return {}
    with STATE_LOCK:
        item = QUEUE_STATE["items"].setdefault(
            key,
            {
                "key": key,
                "target": {
                    "model_id": target.get("model_id"),
                    "version_id": target.get("version_id"),
                    "source_url": target.get("source_url"),
                },
                "created_at": time.time(),
            },
        )
        item.update(values)
        item["updated_at"] = time.time()
        snapshot = dict(item)
    _save_queue(force=force_save, key=key)
    return snapshot


def _queue_summary():
    with STATE_LOCK:
        items = [dict(item) for item in QUEUE_STATE.get("items", {}).values()]
    active = {"queued", "resolving", "downloading", "verifying"}
    resumable = {"interrupted", "error"}
    return {
        "total": len(items),
        "active": sum(1 for item in items if item.get("state") in active),
        "resumable": sum(1 for item in items if item.get("state") in resumable),
        "items": sorted(items, key=lambda item: item.get("updated_at") or 0, reverse=True)[:100],
        "updatedAt": QUEUE_STATE.get("updated_at"),
    }


def _history_limit():
    try:
        value = int(float(_option("civitai_history_limit", 500)))
    except (TypeError, ValueError):
        value = 500
    return max(50, min(value, 5000))


def _append_history(event, **details):
    if not HISTORY_FILE:
        return
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    payload = {"timestamp": time.time(), "event": event, **details}
    with STATE_LOCK:
        with open(HISTORY_FILE, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _history(model_id=None, limit=None):
    limit = limit or _history_limit()
    if not HISTORY_FILE or not os.path.exists(HISTORY_FILE):
        return []
    wanted = str(model_id) if model_id else None
    entries = []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if wanted and str(item.get("modelId")) != wanted:
                    continue
                entries.append(item)
    except OSError:
        return []
    return entries[-limit:][::-1]


def _policy(model_id):
    model_id = LIB._normalize_id(model_id) if LIB else None
    if not model_id:
        return {}
    with STATE_LOCK:
        return dict(LIFECYCLE_STATE.get("policies", {}).get(model_id, {}))


def _set_policy(model_id, action, version_id=None):
    model_id = LIB._normalize_id(model_id) if LIB else None
    version_id = LIB._normalize_id(version_id) if LIB else None
    if not model_id:
        raise ValueError("modelId is required")
    with STATE_LOCK:
        policies = LIFECYCLE_STATE.setdefault("policies", {})
        policy = policies.setdefault(model_id, {"pinned": False, "pinnedVersionId": None, "ignoredVersionIds": [], "updatedAt": None})
        ignored = {value for value in policy.get("ignoredVersionIds", []) if LIB._normalize_id(value)}
        if action == "pin":
            policy["pinned"] = True
            policy["pinnedVersionId"] = version_id
        elif action == "unpin":
            policy["pinned"] = False
            policy["pinnedVersionId"] = None
        elif action == "ignore":
            if not version_id:
                raise ValueError("modelVersionId is required for ignore")
            ignored.add(version_id)
            policy["ignoredVersionIds"] = sorted(ignored, key=int)
        elif action == "unignore":
            ignored.discard(version_id) if version_id else ignored.clear()
            policy["ignoredVersionIds"] = sorted(ignored, key=int)
        else:
            raise ValueError("Unsupported policy action")
        policy["updatedAt"] = time.time()
        snapshot = dict(policy)
    _save_lifecycle()
    if UPD:
        with UPD.UPDATE_LOCK:
            record = UPD.UPDATE_STATE.get("updates", {}).get(model_id)
            if record:
                if action == "pin":
                    record["pinned"] = True
                    record["pinnedVersionId"] = version_id
                elif action == "unpin":
                    record["pinned"] = False
                    record["pinnedVersionId"] = None
                elif action == "ignore" and str(record.get("latestVersionId")) == str(version_id):
                    UPD.UPDATE_STATE.get("updates", {}).pop(model_id, None)
                elif action == "unignore":
                    record["ignoredVersionIds"] = list(snapshot.get("ignoredVersionIds", []))
        try:
            UPD._save_cache()
        except Exception:
            pass
    _append_history("policy", modelId=model_id, modelVersionId=version_id, action=action, policy=snapshot)
    return snapshot


def _reserve_bytes():
    try:
        gb = float(_option("civitai_min_free_space_gb", 5))
    except (TypeError, ValueError):
        gb = 5.0
    return int(max(0, gb) * 1024 * 1024 * 1024)


def _remote_size_bytes(resolved):
    try:
        return max(0, int(float((resolved.get("file") or {}).get("sizeKB") or 0) * 1024))
    except (TypeError, ValueError):
        return 0


def _disk_state(path, required_bytes=0, partial_bytes=0):
    root = path if os.path.isdir(path) else (os.path.dirname(path) or ".")
    reserve = _reserve_bytes()
    remaining = max(0, int(required_bytes) - int(partial_bytes or 0))
    try:
        free = int(shutil.disk_usage(root).free)
    except OSError:
        return {"freeBytes": None, "requiredBytes": int(required_bytes), "remainingBytes": remaining, "reserveBytes": reserve, "ok": True}
    return {"freeBytes": free, "requiredBytes": int(required_bytes), "remainingBytes": remaining, "reserveBytes": reserve, "ok": free - remaining >= reserve}


def _refresh_forge(model_type):
    if not bool(_option("civitai_auto_refresh_forge_models", True)):
        return {"ok": False, "reason": "disabled"}
    try:
        if model_type == "Checkpoint":
            from modules import sd_models
            sd_models.list_models()
            return {"ok": True, "target": "checkpoints"}
        if model_type == "LORA":
            import importlib
            networks = importlib.import_module("networks")
            networks.list_available_networks()
            return {"ok": True, "target": "loras"}
        if model_type == "VAE":
            from modules import sd_vae
            sd_vae.refresh_vae_list()
            return {"ok": True, "target": "vae"}
        if model_type == "TextualInversion":
            from modules import sd_hijack
            embedding_db = getattr(getattr(sd_hijack, "model_hijack", None), "embedding_db", None)
            if embedding_db:
                embedding_db.load_textual_inversion_embeddings(force_reload=True, sync_with_sd_model=False)
                return {"ok": True, "target": "embeddings"}
            return {"ok": False, "reason": "embedding database unavailable"}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:160]}
    return {"ok": False, "reason": f"unsupported refresh target: {model_type}"}


def _range_total(response, start):
    header = str(response.headers.get("content-range") or "")
    match = re.match(r"bytes\s+\d+-\d+/(\d+|\*)", header, flags=re.I)
    if match and match.group(1).isdigit():
        return int(match.group(1))
    length = int(response.headers.get("content-length", 0) or 0)
    return start + length if response.status_code == 206 else length


def _request_download(url, headers, start):
    request_headers = dict(headers)
    if start > 0:
        request_headers["Range"] = f"bytes={start}-"
    return requests.get(url, headers=request_headers, stream=True, timeout=900)


def _smart_download_target(target, api_key):
    if not LIB or not LIB.UI:
        return
    target = LIB.parse_target(target)
    if not target:
        return
    source_key = LIB._target_key(target)
    tracker = f"ID {target['model_id']}"
    LIB.UI.DOWNLOAD_STATUS[tracker] = "Resolving model…"
    _queue_update(target, force_save=True, state="resolving", message="Resolving Civitai metadata")
    partial_path = None
    resolved = None
    destination = None
    try:
        if not LIB.library_summary().get("ready"):
            LIB.UI.DOWNLOAD_STATUS[tracker] = "WAIT · Library index is still building"
            LIB._set_state(source_key, state="indexing", label="Indexing library")
            _queue_update(target, force_save=True, state="interrupted", message="Waiting for Library Intelligence")
            return
        resolved = LIB.resolve_target(target, api_key)
        exact_key = f"{resolved['model_id']}:{resolved['version_id']}"
        resolved_target = {"model_id": resolved["model_id"], "version_id": resolved["version_id"], "source_url": target.get("source_url")}
        old_key = _queue_key(target)
        new_key = _queue_key(resolved_target)
        if old_key and new_key and old_key != new_key:
            with STATE_LOCK:
                QUEUE_STATE.get("items", {}).pop(old_key, None)
            _save_queue(force=True)
        target = resolved_target
        existing_family = LIB._local_model_assets(resolved["model_id"])
        duplicate = LIB._find_duplicate(resolved)
        if duplicate:
            LIB.UI.DOWNLOAD_STATUS.pop(tracker, None)
            tracker = resolved["model_name"]
            LIB.UI.DOWNLOAD_STATUS[tracker] = f"DONE · Already installed · {duplicate.get('path')}"
            state = {"state": "installed", "label": "Installed", "path": duplicate.get("path"), "modelId": resolved["model_id"], "modelVersionId": resolved["version_id"]}
            LIB._set_state(source_key, **state)
            LIB._set_state(exact_key, **state)
            _queue_update(target, force_save=True, state="complete", message="Already installed", destination=duplicate.get("path"), progress=100)
            LIB.UI.FAILED_IDS.discard(source_key)
            return
        LIB.UI.DOWNLOAD_STATUS.pop(tracker, None)
        tracker = resolved["model_name"]
        destination = LIB._choose_destination(resolved)
        partial_path = f"{destination}.part"
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        partial_bytes = os.path.getsize(partial_path) if os.path.exists(partial_path) else 0
        expected_bytes = _remote_size_bytes(resolved)
        disk = _disk_state(destination, expected_bytes, partial_bytes)
        if not disk["ok"]:
            raise RuntimeError("Insufficient disk space while preserving the configured free-space reserve")
        progress0 = (partial_bytes / expected_bytes * 100) if expected_bytes else None
        _queue_update(target, force_save=True, state="queued", message="Queued", modelId=resolved["model_id"], modelVersionId=resolved["version_id"], modelName=resolved["model_name"], modelType=resolved["model_type"], destination=destination, partialPath=partial_path, downloadedBytes=partial_bytes, totalBytes=expected_bytes, progress=progress0)
        LIB._set_state(source_key, state="queued", label="Queued", progress=progress0 or 0, modelId=resolved["model_id"], modelVersionId=resolved["version_id"])
        headers = LIB.UI.build_headers(api_key)
        response = _request_download(resolved["download_url"], headers, partial_bytes)
        if partial_bytes and response.status_code == 416:
            response.close()
            if expected_bytes and partial_bytes >= expected_bytes:
                total_size = expected_bytes
                downloaded = partial_bytes
                response = None
            else:
                try:
                    os.remove(partial_path)
                except OSError:
                    pass
                partial_bytes = 0
                response = _request_download(resolved["download_url"], headers, 0)
                if response.status_code != 200:
                    status = response.status_code
                    response.close()
                    raise RuntimeError(f"Download HTTP {status}")
                total_size = _range_total(response, 0)
                downloaded = 0
        elif response.status_code in (200, 206):
            if partial_bytes and response.status_code == 200:
                partial_bytes = 0
            total_size = _range_total(response, partial_bytes)
            downloaded = partial_bytes
        else:
            status = response.status_code
            response.close()
            raise RuntimeError(f"Download HTTP {status}")
        if response is not None:
            mode = "ab" if partial_bytes and response.status_code == 206 else "wb"
            if mode == "wb":
                downloaded = 0
            started_at = time.time()
            started_bytes = downloaded
            try:
                with response:
                    with open(partial_path, mode) as handle:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if not chunk:
                                continue
                            handle.write(chunk)
                            downloaded += len(chunk)
                            elapsed = max(time.time() - started_at, 0.001)
                            speed = ((downloaded - started_bytes) / (1024 * 1024)) / elapsed
                            progress = min((downloaded / total_size) * 100, 100) if total_size > 0 else None
                            LIB.UI.DOWNLOAD_STATUS[tracker] = f"{progress:5.1f}% · {speed:.1f} MB/s" if progress is not None else f"{downloaded / (1024 * 1024):.1f} MB · {speed:.1f} MB/s"
                            LIB._set_state(source_key, state="downloading", label="Downloading", progress=progress, speedMBs=round(speed, 1), modelId=resolved["model_id"], modelVersionId=resolved["version_id"])
                            _queue_update(target, state="downloading", message="Downloading", downloadedBytes=downloaded, totalBytes=total_size, progress=progress, speedMBs=round(speed, 1))
            except (requests.RequestException, OSError) as exc:
                current = os.path.getsize(partial_path) if os.path.exists(partial_path) else downloaded
                _queue_update(target, force_save=True, state="interrupted", message=f"Transfer interrupted: {str(exc)[:140]}", downloadedBytes=current, totalBytes=total_size)
                raise
        LIB.UI.DOWNLOAD_STATUS[tracker] = "Verifying SHA-256…"
        LIB._set_state(source_key, state="verifying", label="Verifying")
        _queue_update(target, force_save=True, state="verifying", message="Verifying SHA-256", downloadedBytes=os.path.getsize(partial_path), totalBytes=total_size, progress=100)
        downloaded_sha = LIB._sha256_file(partial_path)
        expected_sha = LIB._normalize_sha(resolved.get("sha256"))
        if expected_sha and downloaded_sha != expected_sha:
            try:
                os.remove(partial_path)
            except OSError:
                pass
            raise RuntimeError("SHA-256 mismatch; downloaded file was rejected")
        os.replace(partial_path, destination)
        resolved["sha256"] = expected_sha or downloaded_sha
        LIB._write_sidecars(resolved, destination, api_key)
        LIB._register_downloaded_asset(resolved, destination, resolved["sha256"])
        refresh = _refresh_forge(resolved["model_type"])
        event = "update" if existing_family else "install"
        _append_history(event, modelId=resolved["model_id"], modelVersionId=resolved["version_id"], modelName=resolved["model_name"], modelType=resolved["model_type"], baseModel=resolved.get("base_model"), path=destination, sha256=resolved["sha256"], previousVersionIds=[asset.get("version_id") for asset in existing_family if asset.get("version_id")], forgeRefresh=refresh)
        LIB.UI.DOWNLOAD_STATUS[tracker] = "DONE · Installed"
        installed = {"state": "installed", "label": "Installed", "progress": 100, "path": destination, "modelId": resolved["model_id"], "modelVersionId": resolved["version_id"]}
        LIB._set_state(source_key, **installed)
        LIB._set_state(exact_key, **installed)
        _queue_update(target, force_save=True, state="complete", message="Installed", destination=destination, downloadedBytes=os.path.getsize(destination), totalBytes=os.path.getsize(destination), progress=100, sha256=resolved["sha256"], forgeRefresh=refresh)
        LIB.UI.FAILED_IDS.discard(source_key)
    except Exception as exc:
        current = 0
        if partial_path and os.path.exists(partial_path):
            try:
                current = os.path.getsize(partial_path)
            except OSError:
                pass
        message = str(exc)[:160]
        transient = isinstance(exc, (requests.RequestException, OSError))
        state = "interrupted" if transient and current > 0 else "error"
        LIB.UI.DOWNLOAD_STATUS[tracker] = f"ERROR · {message}"
        LIB.UI.FAILED_IDS.add(source_key)
        LIB._set_state(source_key, state="error", label="Download failed", error=message)
        _queue_update(target, force_save=True, state=state, message=message, downloadedBytes=current, destination=destination, partialPath=partial_path)
        _append_history("download-error", modelId=(resolved or {}).get("model_id") or target.get("model_id"), modelVersionId=(resolved or {}).get("version_id") or target.get("version_id"), modelName=(resolved or {}).get("model_name"), path=destination, error=message, resumable=state == "interrupted", partialBytes=current)


def _scan_one(local_info):
    model_id = local_info["model_id"]
    policy = _policy(model_id)
    model_data = UPD._fetch_model(model_id)
    latest, primary_file = UPD._latest_supported_version(model_data)
    if not latest:
        return None
    latest_id = LIB._normalize_id(latest.get("id"))
    if not latest_id:
        return None
    installed = sorted(local_info.get("installed_version_ids") or set(), key=lambda value: int(value))
    if latest_id in installed:
        return None
    hashes = LIB._file_hashes(primary_file)
    latest_sha = LIB._normalize_sha(hashes.get("SHA256"))
    if latest_sha:
        with LIB.INDEX_LOCK:
            if LIB.INDEX_BY_SHA.get(latest_sha):
                return None
    ignored = {LIB._normalize_id(value) for value in policy.get("ignoredVersionIds", []) if LIB._normalize_id(value)}
    if latest_id in ignored:
        return None
    model_type = str(model_data.get("type") or local_info.get("kind") or "")
    notes = re.sub(r"<[^>]+>", "", str(latest.get("description") or "")).strip()
    if len(notes) > 4000:
        notes = notes[:3997] + "..."
    try:
        size_bytes = int(float(primary_file.get("sizeKB") or 0) * 1024)
    except (TypeError, ValueError):
        size_bytes = 0
    creator = model_data.get("creator") or model_data.get("user") or {}
    creator_name = (creator.get("username") or creator.get("name")) if isinstance(creator, dict) else None
    record = {
        "modelId": str(model_data.get("id") or model_id),
        "modelName": str(model_data.get("name") or local_info.get("model_name") or f"Model {model_id}"),
        "modelType": model_type,
        "installedVersionIds": installed,
        "installedPaths": list(local_info.get("paths") or []),
        "latestVersionId": latest_id,
        "latestVersionName": str(latest.get("name") or latest_id),
        "latestPublishedAt": latest.get("publishedAt") or latest.get("createdAt"),
        "baseModel": latest.get("baseModel") or "Unknown",
        "latestSha256": latest_sha,
        "fileName": primary_file.get("name"),
        "sizeBytes": size_bytes,
        "releaseNotes": notes,
        "creator": creator_name,
        "url": f"https://civitai.com/models/{model_id}?modelVersionId={latest_id}",
        "pinned": bool(policy.get("pinned")),
        "pinnedVersionId": policy.get("pinnedVersionId"),
        "ignoredVersionIds": sorted(ignored, key=int),
    }
    disk = _disk_state(LIB.MODEL_ROOTS.get(model_type, LIB.paths.models_path), size_bytes, 0)
    record["diskSpaceOk"] = disk["ok"]
    record["diskFreeBytes"] = disk["freeBytes"]
    record["diskReserveBytes"] = disk["reserveBytes"]
    return record


def _eligible_for_auto(update, mode):
    if update.get("pinned") or not update.get("diskSpaceOk", True):
        return False
    latest_id = LIB._normalize_id(update.get("latestVersionId"))
    ignored = {LIB._normalize_id(value) for value in update.get("ignoredVersionIds", []) if LIB._normalize_id(value)}
    if latest_id and latest_id in ignored:
        return False
    return ORIGINAL_ELIGIBLE_FOR_AUTO(update, mode)


def _queue_updates(records, limit=None):
    records = list(records or [])
    if limit is not None:
        records = records[:limit]
    eligible = []
    for record in records:
        size_bytes = int(record.get("sizeBytes") or 0)
        model_type = str(record.get("modelType") or "")
        if not _disk_state(LIB.MODEL_ROOTS.get(model_type, LIB.paths.models_path), size_bytes, 0)["ok"]:
            target = {"model_id": str(record.get("modelId") or ""), "version_id": str(record.get("latestVersionId") or ""), "source_url": record.get("url")}
            if target["model_id"]:
                _queue_update(target, force_save=True, state="error", message="Insufficient disk space for update", modelName=record.get("modelName"), modelType=model_type, totalBytes=size_bytes)
            continue
        eligible.append(record)
    targets = [{"model_id": str(item["modelId"]), "version_id": str(item["latestVersionId"]), "source_url": item.get("url")} for item in eligible if item.get("modelId") and item.get("latestVersionId")]
    return LIB.smart_start_downloads(targets, UPD._update_concurrency(), force=True) if targets else 0


def _update_summary():
    summary = ORIGINAL_UPDATE_SUMMARY()
    updates = summary.get("updates", [])
    free_values = [int(item["diskFreeBytes"]) for item in updates if item.get("diskFreeBytes") is not None]
    summary.update({
        "version": "22.7",
        "downloadBytes": sum(int(item.get("sizeBytes") or 0) for item in updates),
        "diskFreeBytes": min(free_values) if free_values else None,
        "reserveBytes": _reserve_bytes(),
        "pinned": sum(1 for item in updates if item.get("pinned")),
        "queue": _queue_summary(),
    })
    return summary


def _resume_loop():
    time.sleep(15)
    if not bool(_option("civitai_resume_downloads_on_startup", True)):
        return
    while LIB and not LIB.library_summary().get("ready"):
        time.sleep(5)
    with STATE_LOCK:
        items = [dict(item) for item in QUEUE_STATE.get("items", {}).values() if item.get("state") == "interrupted"]
    for item in items:
        target = LIB.parse_target(item.get("target") or {})
        if target:
            _append_history("resume", modelId=target.get("model_id"), modelVersionId=target.get("version_id"), partialBytes=item.get("downloadedBytes", 0))
            LIB.smart_start_downloads([target], 1, force=True)


def _start_resume_once():
    global RESUME_STARTED
    with RESUME_LOCK:
        if RESUME_STARTED:
            return
        RESUME_STARTED = True
    threading.Thread(target=_resume_loop, daemon=True).start()


def register_api(_: object, app: FastAPI):
    @app.get("/civitaiflow/api/lifecycle")
    async def lifecycle(request: Request):
        LIB._require_local(request)
        return {"ok": True, "version": "22.7", "queue": _queue_summary(), "policies": dict(LIFECYCLE_STATE.get("policies", {})), "history": _history(limit=50), "reserveBytes": _reserve_bytes()}

    @app.get("/civitaiflow/api/history")
    async def history(request: Request, modelId: str = None):
        LIB._require_local(request)
        return {"ok": True, "history": _history(model_id=LIB._normalize_id(modelId) if modelId else None)}

    @app.post("/civitaiflow/api/policy")
    async def policy(request: Request, payload: dict = Body(default_factory=dict)):
        LIB._require_local(request)
        try:
            value = _set_policy(payload.get("modelId"), str(payload.get("action") or ""), payload.get("modelVersionId"))
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "policy": value}

    @app.post("/civitaiflow/api/queue/resume")
    async def resume_queue(request: Request):
        LIB._require_local(request)
        with STATE_LOCK:
            targets = [item.get("target") for item in QUEUE_STATE.get("items", {}).values() if item.get("state") in {"interrupted", "error"}]
        targets = [LIB.parse_target(target) for target in targets]
        queued = LIB.smart_start_downloads([target for target in targets if target], 1, force=True)
        return {"ok": True, "queued": queued, "queue": _queue_summary()}

    @app.post("/civitaiflow/api/queue/forget-completed")
    async def forget_completed(request: Request):
        LIB._require_local(request)
        with STATE_LOCK:
            QUEUE_STATE["items"] = {key: item for key, item in QUEUE_STATE.get("items", {}).items() if item.get("state") != "complete"}
        _save_queue(force=True)
        return {"ok": True, "queue": _queue_summary()}

    _start_resume_once()


def _patch_runtime():
    global ORIGINAL_ELIGIBLE_FOR_AUTO, ORIGINAL_UPDATE_SUMMARY
    if not LIB or not UPD:
        return
    LIB.smart_download_target = _smart_download_target
    ORIGINAL_ELIGIBLE_FOR_AUTO = UPD._eligible_for_auto
    ORIGINAL_UPDATE_SUMMARY = UPD.update_summary
    UPD._scan_one = _scan_one
    UPD._eligible_for_auto = _eligible_for_auto
    UPD._queue_updates = _queue_updates
    UPD.update_summary = _update_summary


_load_state()
_patch_runtime()
if LIB and UPD:
    script_callbacks.on_app_started(register_api)
