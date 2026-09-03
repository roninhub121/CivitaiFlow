import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import gradio as gr
import requests
from fastapi import Body, FastAPI, Request
from modules import script_callbacks, script_loading, shared


UPDATE_SCHEMA_VERSION = 1
UPDATE_LOCK = threading.RLock()
SCHEDULER_LOCK = threading.RLock()
SCHEDULER_STARTED = False


def _find_library_module():
    for script_path, module in script_loading.loaded_scripts.items():
        if os.path.basename(script_path).lower() == "zz_civitaiflow_library.py":
            return module
    return None


LIB = _find_library_module()
UPDATE_FILE = os.path.join(LIB.DATA_DIR, "update-cache.json") if LIB else None

UPDATE_STATE = {
    "schema": UPDATE_SCHEMA_VERSION,
    "running": False,
    "last_scan": None,
    "last_reason": None,
    "checked": 0,
    "total": 0,
    "errors": 0,
    "message": "Updates have not been checked yet",
    "updates": {},
}


def on_ui_settings():
    section = ("civitai_flow", "CivitaiFlow Manager")
    shared.opts.add_option(
        "civitai_update_mode",
        shared.OptionInfo(
            "Notify only",
            "Model update behavior",
            gr.Radio,
            {
                "choices": [
                    "Disabled",
                    "Notify only",
                    "Auto-download LoRAs (keep old)",
                    "Auto-download LoRAs + checkpoints (keep old)",
                ]
            },
            section=section,
        ),
    )
    shared.opts.add_option(
        "civitai_update_interval_hours",
        shared.OptionInfo(
            24,
            "Check Civitai model updates every N hours",
            gr.Number,
            {"precision": 0},
            section=section,
        ),
    )
    shared.opts.add_option(
        "civitai_update_concurrency",
        shared.OptionInfo(
            2,
            "Auto-update concurrent downloads",
            gr.Number,
            {"precision": 0},
            section=section,
        ),
    )
    shared.opts.add_option(
        "civitai_update_max_per_cycle",
        shared.OptionInfo(
            10,
            "Maximum automatic model updates per scan",
            gr.Number,
            {"precision": 0},
            section=section,
        ),
    )
    shared.opts.add_option(
        "civitai_update_check_on_startup",
        shared.OptionInfo(
            True,
            "Check for Civitai model updates after Forge starts",
            section=section,
        ),
    )


script_callbacks.on_ui_settings(on_ui_settings)


def _option(name, default):
    try:
        return getattr(shared.opts, name)
    except Exception:
        return shared.opts.data.get(name, default)


def _update_mode():
    return str(_option("civitai_update_mode", "Notify only") or "Notify only")


def _interval_seconds():
    try:
        hours = int(float(_option("civitai_update_interval_hours", 24)))
    except (TypeError, ValueError):
        hours = 24
    return max(1, min(hours, 24 * 30)) * 3600


def _update_concurrency():
    try:
        value = int(float(_option("civitai_update_concurrency", 2)))
    except (TypeError, ValueError):
        value = 2
    return max(1, min(value, 5))


def _max_auto_updates():
    try:
        value = int(float(_option("civitai_update_max_per_cycle", 10)))
    except (TypeError, ValueError):
        value = 10
    return max(1, min(value, 100))


def _load_cache():
    if not UPDATE_FILE:
        return
    try:
        with open(UPDATE_FILE, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("schema") != UPDATE_SCHEMA_VERSION:
            return
        with UPDATE_LOCK:
            UPDATE_STATE.update(
                {
                    "last_scan": payload.get("last_scan"),
                    "last_reason": payload.get("last_reason"),
                    "checked": payload.get("checked", 0),
                    "total": payload.get("total", 0),
                    "errors": payload.get("errors", 0),
                    "message": payload.get("message", "Cached update scan loaded"),
                    "updates": payload.get("updates", {}) if isinstance(payload.get("updates"), dict) else {},
                }
            )
    except (OSError, ValueError, TypeError):
        return


def _save_cache():
    if not UPDATE_FILE:
        return
    os.makedirs(os.path.dirname(UPDATE_FILE), exist_ok=True)
    with UPDATE_LOCK:
        payload = {
            "schema": UPDATE_SCHEMA_VERSION,
            "last_scan": UPDATE_STATE.get("last_scan"),
            "last_reason": UPDATE_STATE.get("last_reason"),
            "checked": UPDATE_STATE.get("checked", 0),
            "total": UPDATE_STATE.get("total", 0),
            "errors": UPDATE_STATE.get("errors", 0),
            "message": UPDATE_STATE.get("message"),
            "updates": UPDATE_STATE.get("updates", {}),
        }
    temp_path = f"{UPDATE_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    os.replace(temp_path, UPDATE_FILE)


_load_cache()


def _published_key(version):
    timestamp = str(version.get("publishedAt") or version.get("createdAt") or "")
    try:
        version_id = int(version.get("id") or 0)
    except (TypeError, ValueError):
        version_id = 0
    return timestamp, version_id


def _latest_supported_version(model_data):
    versions = list(model_data.get("modelVersions") or [])
    versions.sort(key=_published_key, reverse=True)
    for version in versions:
        try:
            primary_file = LIB._select_primary_file(version)
        except Exception:
            continue
        return version, primary_file
    return None, None


def _installed_models_snapshot():
    models = {}
    with LIB.INDEX_LOCK:
        assets = list(LIB.LIBRARY.get("assets", {}).values())

    for asset in assets:
        model_id = LIB._normalize_id(asset.get("model_id"))
        if not model_id:
            continue
        entry = models.setdefault(
            model_id,
            {
                "model_id": model_id,
                "installed_version_ids": set(),
                "paths": [],
                "kind": asset.get("civitai_type") or asset.get("kind"),
                "model_name": asset.get("model_name"),
            },
        )
        version_id = LIB._normalize_id(asset.get("version_id"))
        if version_id:
            entry["installed_version_ids"].add(version_id)
        path = asset.get("path")
        if path and path not in entry["paths"]:
            entry["paths"].append(path)
        if not entry.get("model_name") and asset.get("model_name"):
            entry["model_name"] = asset.get("model_name")
        if not entry.get("kind"):
            entry["kind"] = asset.get("civitai_type") or asset.get("kind")
    return models


def _fetch_model(model_id):
    if not LIB or not LIB.UI:
        raise RuntimeError("CivitaiFlow Library Intelligence is not loaded")
    response = requests.get(
        f"{LIB.UI.CIVITAI_API_URL}/models/{model_id}",
        headers=LIB.UI.build_headers(LIB.UI.get_api_key()),
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Civitai model API returned HTTP {response.status_code}")
    return response.json()


def _scan_one(local_info):
    model_id = local_info["model_id"]
    model_data = _fetch_model(model_id)
    latest, primary_file = _latest_supported_version(model_data)
    if not latest:
        return None

    latest_id = LIB._normalize_id(latest.get("id"))
    if not latest_id:
        return None

    installed_versions = sorted(local_info.get("installed_version_ids") or set(), key=lambda value: int(value))
    if latest_id in installed_versions:
        return None

    hashes = LIB._file_hashes(primary_file)
    latest_sha = LIB._normalize_sha(hashes.get("SHA256"))
    if latest_sha:
        with LIB.INDEX_LOCK:
            if LIB.INDEX_BY_SHA.get(latest_sha):
                return None

    model_type = str(model_data.get("type") or local_info.get("kind") or "")
    return {
        "modelId": str(model_data.get("id") or model_id),
        "modelName": str(model_data.get("name") or local_info.get("model_name") or f"Model {model_id}"),
        "modelType": model_type,
        "installedVersionIds": installed_versions,
        "installedPaths": list(local_info.get("paths") or []),
        "latestVersionId": latest_id,
        "latestVersionName": str(latest.get("name") or latest_id),
        "latestPublishedAt": latest.get("publishedAt") or latest.get("createdAt"),
        "baseModel": latest.get("baseModel") or "Unknown",
        "latestSha256": latest_sha,
        "fileName": primary_file.get("name"),
        "url": f"https://civitai.com/models/{model_id}?modelVersionId={latest_id}",
    }


def _eligible_for_auto(update, mode):
    model_type = str(update.get("modelType") or "")
    if mode == "Auto-download LoRAs (keep old)":
        return model_type == "LORA"
    if mode == "Auto-download LoRAs + checkpoints (keep old)":
        return model_type in {"LORA", "Checkpoint"}
    return False


def _queue_updates(records, limit=None):
    if not LIB or not records:
        return 0
    if limit is not None:
        records = list(records)[:limit]
    targets = [
        {
            "model_id": str(item["modelId"]),
            "version_id": str(item["latestVersionId"]),
            "source_url": item.get("url"),
        }
        for item in records
        if item.get("modelId") and item.get("latestVersionId")
    ]
    return LIB.smart_start_downloads(targets, _update_concurrency(), force=True)


def _scan_worker(reason):
    if not LIB:
        with UPDATE_LOCK:
            UPDATE_STATE.update(
                {
                    "running": False,
                    "message": "Library Intelligence is unavailable",
                    "errors": 1,
                }
            )
        return

    summary = LIB.library_summary()
    if not summary.get("ready"):
        with UPDATE_LOCK:
            UPDATE_STATE.update(
                {
                    "running": False,
                    "message": "Library index is not ready yet",
                }
            )
        return

    local_models = _installed_models_snapshot()
    total = len(local_models)
    updates = {}
    errors = 0
    checked = 0

    with UPDATE_LOCK:
        UPDATE_STATE.update(
            {
                "running": True,
                "last_reason": reason,
                "checked": 0,
                "total": total,
                "errors": 0,
                "message": f"Checking Civitai updates · 0/{total}",
            }
        )

    max_workers = min(4, max(1, total))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_scan_one, info): model_id
            for model_id, info in local_models.items()
        }
        for future in as_completed(futures):
            checked += 1
            try:
                record = future.result()
                if record:
                    updates[str(record["modelId"])] = record
            except Exception:
                errors += 1
            with UPDATE_LOCK:
                UPDATE_STATE.update(
                    {
                        "checked": checked,
                        "errors": errors,
                        "message": f"Checking Civitai updates · {checked}/{total}",
                    }
                )

    now = time.time()
    with UPDATE_LOCK:
        UPDATE_STATE.update(
            {
                "running": False,
                "last_scan": now,
                "last_reason": reason,
                "checked": checked,
                "total": total,
                "errors": errors,
                "updates": updates,
                "message": f"Update scan complete · {len(updates)} available",
            }
        )
    _save_cache()

    mode = _update_mode()
    auto_records = [record for record in updates.values() if _eligible_for_auto(record, mode)]
    if auto_records:
        queued = _queue_updates(auto_records, limit=_max_auto_updates())
        with UPDATE_LOCK:
            UPDATE_STATE["message"] = (
                f"Update scan complete · {len(updates)} available · {queued} auto-update(s) queued"
            )
        _save_cache()


def start_update_scan(reason="manual"):
    with UPDATE_LOCK:
        if UPDATE_STATE.get("running"):
            return False
        UPDATE_STATE["running"] = True
        UPDATE_STATE["message"] = "Starting update scan"
    threading.Thread(target=_scan_worker, args=(reason,), daemon=True).start()
    return True


def _live_updates():
    with UPDATE_LOCK:
        cached = [dict(item) for item in UPDATE_STATE.get("updates", {}).values()]

    live = []
    for item in cached:
        target = {
            "model_id": item.get("modelId"),
            "version_id": item.get("latestVersionId"),
        }
        try:
            status = LIB.status_for_target(target)
        except Exception:
            status = {"state": "available", "label": "Update available"}
        if status.get("state") == "installed":
            continue
        item["state"] = status.get("state") or "available"
        item["stateLabel"] = status.get("label") or "Update available"
        if status.get("progress") is not None:
            item["progress"] = status.get("progress")
        live.append(item)

    live.sort(key=lambda item: (item.get("modelType") != "LORA", item.get("modelName", "").lower()))
    return live


def update_summary():
    with UPDATE_LOCK:
        state = {
            "running": UPDATE_STATE.get("running", False),
            "lastScan": UPDATE_STATE.get("last_scan"),
            "lastReason": UPDATE_STATE.get("last_reason"),
            "checked": UPDATE_STATE.get("checked", 0),
            "total": UPDATE_STATE.get("total", 0),
            "errors": UPDATE_STATE.get("errors", 0),
            "message": UPDATE_STATE.get("message"),
        }
    updates = _live_updates() if LIB else []
    return {
        **state,
        "mode": _update_mode(),
        "intervalHours": int(_interval_seconds() / 3600),
        "available": len(updates),
        "updates": updates,
    }


def _scheduler_loop():
    time.sleep(12)
    startup_scan_done = False
    while True:
        try:
            if not LIB or not LIB.library_summary().get("ready"):
                time.sleep(15)
                continue

            mode = _update_mode()
            if mode == "Disabled":
                time.sleep(300)
                continue

            with UPDATE_LOCK:
                last_scan = UPDATE_STATE.get("last_scan") or 0

            startup_enabled = bool(_option("civitai_update_check_on_startup", True))
            due = (time.time() - float(last_scan or 0)) >= _interval_seconds()
            if startup_enabled and not startup_scan_done and not last_scan:
                due = True

            if due:
                start_update_scan(reason="scheduled")
                startup_scan_done = True
            time.sleep(60)
        except Exception:
            time.sleep(60)


def _start_scheduler_once():
    global SCHEDULER_STARTED
    with SCHEDULER_LOCK:
        if SCHEDULER_STARTED:
            return
        SCHEDULER_STARTED = True
    threading.Thread(target=_scheduler_loop, daemon=True).start()


def register_update_api(_: object, app: FastAPI):
    @app.get("/civitaiflow/api/updates")
    async def civitaiflow_updates(request: Request):
        LIB._require_local(request)
        return {"ok": True, "version": "22.6", **update_summary()}

    @app.post("/civitaiflow/api/updates/scan")
    async def civitaiflow_updates_scan(request: Request):
        LIB._require_local(request)
        started = start_update_scan(reason="manual")
        return {"ok": True, "started": started, **update_summary()}

    @app.post("/civitaiflow/api/updates/apply")
    async def civitaiflow_updates_apply(request: Request, payload: dict = Body(default_factory=dict)):
        LIB._require_local(request)
        model_id = LIB._normalize_id(payload.get("modelId"))
        if not model_id:
            return {"ok": False, "queued": 0, "error": "modelId is required"}
        record = next((item for item in _live_updates() if str(item.get("modelId")) == model_id), None)
        if not record:
            return {"ok": True, "queued": 0, "state": "current"}
        queued = _queue_updates([record])
        return {"ok": True, "queued": queued, "modelId": model_id, "latestVersionId": record.get("latestVersionId")}

    @app.post("/civitaiflow/api/updates/apply-all")
    async def civitaiflow_updates_apply_all(request: Request):
        LIB._require_local(request)
        updates = _live_updates()
        queued = _queue_updates(updates)
        return {"ok": True, "queued": queued, "requested": len(updates)}

    _start_scheduler_once()


if LIB:
    script_callbacks.on_app_started(register_update_api)
