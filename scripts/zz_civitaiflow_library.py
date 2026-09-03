import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlparse

import requests
from fastapi import Body, FastAPI, HTTPException, Request
from modules import paths, script_callbacks, script_loading


INDEX_SCHEMA_VERSION = 1
DATA_DIR = os.path.join(paths.data_path, "civitai-flow")
INDEX_FILE = os.path.join(DATA_DIR, "library-index.json")

MODEL_ROOTS = {
    "LORA": os.path.join(paths.models_path, "Lora"),
    "Checkpoint": os.path.join(paths.models_path, "Stable-diffusion"),
    "VAE": os.path.join(paths.models_path, "VAE"),
    "TextualInversion": os.path.join(paths.data_path, "embeddings"),
}

SUPPORTED_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".bin"}
REMOTE_CACHE_TTL = 180

INDEX_LOCK = threading.RLock()
REMOTE_LOCK = threading.RLock()
STATE_LOCK = threading.RLock()

LIBRARY = {
    "schema": INDEX_SCHEMA_VERSION,
    "assets": {},
    "updated_at": None,
}
INDEX_BY_SHA = {}
INDEX_BY_MODEL = {}
INDEX_BY_VERSION = {}
REMOTE_CACHE = {}
SMART_STATES = {}
INDEX_STATE = {
    "ready": False,
    "running": False,
    "processed": 0,
    "total": 0,
    "hashed": 0,
    "message": "Waiting to index library",
    "error": None,
}


def _find_ui_module():
    for script_path, module in script_loading.loaded_scripts.items():
        if os.path.basename(script_path).lower() == "ronin_ui.py":
            return module
    return None


UI = _find_ui_module()


def _safe_component(value, fallback="General"):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "")).strip(" .")
    return value[:140] or fallback


def _normalize_id(value):
    value = str(value or "").strip()
    return value if value.isdigit() else None


def _target_key(target):
    model_id = _normalize_id(target.get("model_id")) or "unknown"
    version_id = _normalize_id(target.get("version_id")) or "latest"
    return f"{model_id}:{version_id}"


def _normalize_sha(value):
    value = str(value or "").strip().upper()
    return value if re.fullmatch(r"[A-F0-9]{64}", value) else None


def _load_index():
    global LIBRARY
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if data.get("schema") == INDEX_SCHEMA_VERSION and isinstance(data.get("assets"), dict):
            LIBRARY = data
    except (OSError, ValueError, TypeError):
        LIBRARY = {
            "schema": INDEX_SCHEMA_VERSION,
            "assets": {},
            "updated_at": None,
        }


_load_index()


def _save_index():
    os.makedirs(DATA_DIR, exist_ok=True)
    temp_path = f"{INDEX_FILE}.tmp"
    payload = {
        "schema": INDEX_SCHEMA_VERSION,
        "assets": LIBRARY.get("assets", {}),
        "updated_at": time.time(),
    }
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    os.replace(temp_path, INDEX_FILE)
    LIBRARY["updated_at"] = payload["updated_at"]


def _rebuild_lookup_maps():
    global INDEX_BY_SHA, INDEX_BY_MODEL, INDEX_BY_VERSION
    by_sha = {}
    by_model = {}
    by_version = {}

    for asset in LIBRARY.get("assets", {}).values():
        sha = _normalize_sha(asset.get("sha256"))
        model_id = _normalize_id(asset.get("model_id"))
        version_id = _normalize_id(asset.get("version_id"))
        if sha:
            by_sha.setdefault(sha, []).append(asset)
        if model_id:
            by_model.setdefault(model_id, []).append(asset)
        if version_id:
            by_version.setdefault(version_id, []).append(asset)

    INDEX_BY_SHA = by_sha
    INDEX_BY_MODEL = by_model
    INDEX_BY_VERSION = by_version


with INDEX_LOCK:
    _rebuild_lookup_maps()


def _read_sidecar(model_path):
    base, _ = os.path.splitext(model_path)
    sidecar_path = f"{base}.json"
    try:
        with open(sidecar_path, "r", encoding="utf-8") as handle:
            metadata = json.load(handle)
        return {
            "model_id": _normalize_id(metadata.get("civitai model id")),
            "version_id": _normalize_id(metadata.get("civitai version id")),
            "sha256": _normalize_sha(metadata.get("civitai file sha256")),
            "file_name": metadata.get("civitai file name"),
        }
    except (OSError, ValueError, TypeError):
        return {}


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(4 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().upper()


def _collect_library_files():
    files = []
    for kind, root in MODEL_ROOTS.items():
        if not os.path.isdir(root):
            continue
        for current_root, _, names in os.walk(root):
            for name in names:
                extension = os.path.splitext(name)[1].lower()
                if extension not in SUPPORTED_EXTENSIONS:
                    continue
                files.append((os.path.abspath(os.path.join(current_root, name)), kind))
    return files


def _resolve_unknown_hashes(assets):
    if not UI:
        return

    unknown_hashes = []
    seen = set()
    for asset in assets:
        sha = _normalize_sha(asset.get("sha256"))
        if not sha or asset.get("model_id") or sha in seen:
            continue
        seen.add(sha)
        unknown_hashes.append(sha)

    if not unknown_hashes:
        return

    headers = UI.build_headers(UI.get_api_key())
    endpoint = f"{UI.CIVITAI_API_URL}/model-versions/by-hash"
    resolved = {}

    for offset in range(0, len(unknown_hashes), 100):
        batch = unknown_hashes[offset : offset + 100]
        try:
            response = requests.post(endpoint, json=batch, headers=headers, timeout=45)
            if response.status_code != 200:
                continue
            versions = response.json() or []
        except (requests.RequestException, ValueError):
            continue

        for version in versions:
            model_id = _normalize_id(version.get("modelId"))
            version_id = _normalize_id(version.get("id"))
            model = version.get("model") or {}
            model_name = model.get("name")
            model_type = model.get("type")
            for file_info in version.get("files") or []:
                hashes = file_info.get("hashes") or {}
                if isinstance(hashes, list):
                    hashes = {
                        str(item.get("type")): item.get("hash")
                        for item in hashes
                        if isinstance(item, dict)
                    }
                sha = _normalize_sha(hashes.get("SHA256"))
                if sha:
                    resolved[sha] = {
                        "model_id": model_id,
                        "version_id": version_id,
                        "model_name": model_name,
                        "civitai_type": model_type,
                    }

    if not resolved:
        return

    for asset in assets:
        hit = resolved.get(_normalize_sha(asset.get("sha256")))
        if not hit:
            continue
        if not asset.get("model_id"):
            asset["model_id"] = hit.get("model_id")
        if not asset.get("version_id"):
            asset["version_id"] = hit.get("version_id")
        if not asset.get("model_name"):
            asset["model_name"] = hit.get("model_name")
        if not asset.get("civitai_type"):
            asset["civitai_type"] = hit.get("civitai_type")


def _scan_library_worker():
    files = _collect_library_files()
    with STATE_LOCK:
        INDEX_STATE.update(
            {
                "ready": False,
                "running": True,
                "processed": 0,
                "total": len(files),
                "hashed": 0,
                "message": "Indexing Forge model library",
                "error": None,
            }
        )

    previous_assets = dict(LIBRARY.get("assets", {}))
    next_assets = {}

    try:
        for index, (path, kind) in enumerate(files, start=1):
            try:
                stat = os.stat(path)
            except OSError:
                continue

            cache = previous_assets.get(path) or {}
            unchanged = (
                cache.get("size") == stat.st_size
                and cache.get("mtime_ns") == stat.st_mtime_ns
                and _normalize_sha(cache.get("sha256"))
            )

            sidecar = _read_sidecar(path)
            sha = _normalize_sha(sidecar.get("sha256")) or (
                _normalize_sha(cache.get("sha256")) if unchanged else None
            )

            if not sha:
                sha = _sha256_file(path)
                with STATE_LOCK:
                    INDEX_STATE["hashed"] += 1

            asset = {
                "path": path,
                "name": os.path.basename(path),
                "kind": kind,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": sha,
                "model_id": sidecar.get("model_id") or cache.get("model_id"),
                "version_id": sidecar.get("version_id") or cache.get("version_id"),
                "model_name": cache.get("model_name"),
                "civitai_type": cache.get("civitai_type"),
            }
            next_assets[path] = asset

            with STATE_LOCK:
                INDEX_STATE["processed"] = index
                INDEX_STATE["message"] = f"Indexing model library · {index}/{len(files)}"

        _resolve_unknown_hashes(list(next_assets.values()))

        with INDEX_LOCK:
            LIBRARY["assets"] = next_assets
            _rebuild_lookup_maps()
            _save_index()

        with STATE_LOCK:
            INDEX_STATE.update(
                {
                    "ready": True,
                    "running": False,
                    "processed": len(files),
                    "total": len(files),
                    "message": f"Library ready · {len(files)} assets indexed",
                    "error": None,
                }
            )
    except Exception as exc:
        with STATE_LOCK:
            INDEX_STATE.update(
                {
                    "ready": False,
                    "running": False,
                    "message": "Library index failed",
                    "error": str(exc)[:180],
                }
            )


def start_library_index(force=False):
    with STATE_LOCK:
        if INDEX_STATE.get("running"):
            return False
        if INDEX_STATE.get("ready") and not force:
            return False
        INDEX_STATE["running"] = True
        INDEX_STATE["ready"] = False

    threading.Thread(target=_scan_library_worker, daemon=True).start()
    return True


def library_summary():
    with INDEX_LOCK:
        assets = list(LIBRARY.get("assets", {}).values())
    counts = {}
    for asset in assets:
        counts[asset.get("kind") or "Other"] = counts.get(asset.get("kind") or "Other", 0) + 1
    with STATE_LOCK:
        state = dict(INDEX_STATE)
    return {
        "ready": state.get("ready", False),
        "running": state.get("running", False),
        "processed": state.get("processed", 0),
        "total": state.get("total", 0),
        "hashed": state.get("hashed", 0),
        "message": state.get("message"),
        "error": state.get("error"),
        "assets": len(assets),
        "counts": counts,
        "updatedAt": LIBRARY.get("updated_at"),
    }


def parse_target(value):
    if isinstance(value, dict):
        model_id = _normalize_id(value.get("model_id") or value.get("modelId"))
        version_id = _normalize_id(value.get("version_id") or value.get("modelVersionId"))
        source_url = value.get("source_url") or value.get("url")
        if model_id:
            return {"model_id": model_id, "version_id": version_id, "source_url": source_url}
        return None

    raw = str(value or "").strip()
    if not raw:
        return None

    compact = re.fullmatch(r"(\d+)(?::(\d+|latest))?", raw)
    if compact:
        return {
            "model_id": compact.group(1),
            "version_id": compact.group(2) if compact.group(2) and compact.group(2) != "latest" else None,
            "source_url": None,
        }

    match = re.search(r"(?:https?://)?(?:www\.)?civitai\.com/models/(\d+)([^\s]*)", raw, re.I)
    if not match:
        return None

    model_id = match.group(1)
    version_id = None
    try:
        parsed = urlparse(raw if raw.startswith("http") else f"https://{raw}")
        version_id = _normalize_id((parse_qs(parsed.query).get("modelVersionId") or [None])[0])
    except ValueError:
        version_id = None

    return {
        "model_id": model_id,
        "version_id": version_id,
        "source_url": raw,
    }


def parse_civitai_targets(text):
    text = text or ""
    candidates = re.findall(
        r"https?://(?:www\.)?civitai\.com/models/\d+[^\s<>'\"]*",
        text,
        flags=re.I,
    )
    candidates.extend(re.findall(r"^\s*\d+(?::\d+)?\s*$", text, flags=re.M))

    results = []
    seen = set()
    for candidate in candidates:
        target = parse_target(candidate.strip())
        if not target:
            continue
        key = _target_key(target)
        if key in seen:
            continue
        seen.add(key)
        results.append(target)
    return results


def _remote_model(model_id, api_key):
    now = time.time()
    with REMOTE_LOCK:
        cached = REMOTE_CACHE.get(model_id)
        if cached and now - cached[0] < REMOTE_CACHE_TTL:
            return cached[1]

    response = requests.get(
        f"{UI.CIVITAI_API_URL}/models/{model_id}",
        headers=UI.build_headers(api_key),
        timeout=25,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Civitai model API returned HTTP {response.status_code}")
    data = response.json()
    with REMOTE_LOCK:
        REMOTE_CACHE[model_id] = (now, data)
    return data


def _file_hashes(file_info):
    hashes = file_info.get("hashes") or {}
    if isinstance(hashes, list):
        hashes = {
            str(item.get("type")): item.get("hash")
            for item in hashes
            if isinstance(item, dict)
        }
    return hashes


def _select_version(model_data, requested_version_id):
    versions = model_data.get("modelVersions") or []
    if not versions:
        raise RuntimeError("No downloadable model versions found")

    if requested_version_id:
        for version in versions:
            if str(version.get("id")) == str(requested_version_id):
                return version
        raise RuntimeError(f"Requested modelVersionId {requested_version_id} is not available")
    return versions[0]


def _select_primary_file(version):
    files = version.get("files") or []
    candidates = []
    for file_info in files:
        extension = os.path.splitext(str(file_info.get("name") or ""))[1].lower()
        if extension not in SUPPORTED_EXTENSIONS:
            continue
        if file_info.get("type") == "Model":
            candidates.append(file_info)

    if not candidates:
        candidates = [
            file_info
            for file_info in files
            if os.path.splitext(str(file_info.get("name") or ""))[1].lower() in SUPPORTED_EXTENSIONS
        ]

    if not candidates:
        raise RuntimeError("No supported model file found in this version")

    return next((item for item in candidates if item.get("primary") is True), candidates[0])


def _target_directory(model_data, model_type):
    root = MODEL_ROOTS.get(model_type)
    if not root:
        raise RuntimeError(f"Unsupported Civitai model type: {model_type}")

    if model_type == "LORA":
        tag = (model_data.get("tags") or ["General"])[0]
        return os.path.join(root, _safe_component(tag))
    return root


def resolve_target(target, api_key=None):
    if not UI:
        raise RuntimeError("CivitaiFlow UI module is not loaded")

    target = parse_target(target)
    if not target:
        raise RuntimeError("Invalid Civitai model target")

    api_key = api_key if api_key is not None else UI.get_api_key()
    model_data = _remote_model(target["model_id"], api_key)
    version = _select_version(model_data, target.get("version_id"))
    primary_file = _select_primary_file(version)

    model_type = str(model_data.get("type") or "").strip()
    target_dir = _target_directory(model_data, model_type)
    clean_model_name = _safe_component(model_data.get("name"), f"model-{target['model_id']}")
    source_name = _safe_component(primary_file.get("name"), f"{clean_model_name}.safetensors")
    extension = os.path.splitext(source_name)[1].lower() or ".safetensors"
    if extension not in SUPPORTED_EXTENSIONS:
        extension = ".safetensors"
        source_name = f"{os.path.splitext(source_name)[0]}{extension}"

    hashes = _file_hashes(primary_file)
    sha256 = _normalize_sha(hashes.get("SHA256"))
    download_url = primary_file.get("downloadUrl") or (
        f"{UI.CIVITAI_BASE_URL}/api/download/models/{version['id']}"
    )

    return {
        "target": target,
        "model_id": str(model_data.get("id") or target["model_id"]),
        "version_id": str(version.get("id")),
        "model_name": clean_model_name,
        "model_type": model_type,
        "version_name": str(version.get("name") or version.get("id")),
        "base_model": version.get("baseModel") or "Unknown",
        "trained_words": version.get("trainedWords") or [],
        "description": model_data.get("description") or version.get("description") or "",
        "images": version.get("images") or [],
        "file": primary_file,
        "file_name": source_name,
        "sha256": sha256,
        "download_url": download_url,
        "target_dir": target_dir,
    }


def _find_duplicate(resolved):
    sha = _normalize_sha(resolved.get("sha256"))
    version_id = _normalize_id(resolved.get("version_id"))
    with INDEX_LOCK:
        if sha and INDEX_BY_SHA.get(sha):
            return INDEX_BY_SHA[sha][0]
        if version_id and INDEX_BY_VERSION.get(version_id):
            return INDEX_BY_VERSION[version_id][0]
    return None


def _local_model_assets(model_id):
    model_id = _normalize_id(model_id)
    if not model_id:
        return []
    with INDEX_LOCK:
        return list(INDEX_BY_MODEL.get(model_id, []))


def _state_for_key(key):
    with STATE_LOCK:
        value = SMART_STATES.get(key)
        return dict(value) if value else None


def _set_state(key, **values):
    with STATE_LOCK:
        state = SMART_STATES.setdefault(key, {})
        state.update(values)
        state["updated_at"] = time.time()
        return dict(state)


def status_for_target(target):
    target = parse_target(target)
    if not target:
        return {"state": "error", "label": "Invalid model link"}

    summary = library_summary()
    if not summary["ready"]:
        return {
            "state": "indexing",
            "label": summary.get("message") or "Indexing library",
            "index": summary,
        }

    key = _target_key(target)
    active = _state_for_key(key)
    if active and active.get("state") in {"queued", "downloading", "verifying"}:
        return {**active, "index": summary}

    model_assets = _local_model_assets(target["model_id"])
    requested_version = _normalize_id(target.get("version_id"))

    if requested_version:
        with INDEX_LOCK:
            exact = list(INDEX_BY_VERSION.get(requested_version, []))
        if exact:
            return {
                "state": "installed",
                "label": "Installed",
                "path": exact[0].get("path"),
                "modelId": target["model_id"],
                "modelVersionId": requested_version,
                "index": summary,
            }
        if model_assets:
            return {
                "state": "update",
                "label": "Different version installed",
                "installedVersionId": model_assets[0].get("version_id"),
                "modelVersionId": requested_version,
                "index": summary,
            }
        return {"state": "available", "label": "Send to Forge", "index": summary}

    if not model_assets:
        return {"state": "available", "label": "Send to Forge", "index": summary}

    try:
        resolved = resolve_target(target)
        duplicate = _find_duplicate(resolved)
        if duplicate:
            return {
                "state": "installed",
                "label": "Installed",
                "path": duplicate.get("path"),
                "modelId": resolved["model_id"],
                "modelVersionId": resolved["version_id"],
                "index": summary,
            }
        return {
            "state": "update",
            "label": "Update available",
            "installedVersionId": model_assets[0].get("version_id"),
            "modelVersionId": resolved["version_id"],
            "index": summary,
        }
    except Exception:
        return {
            "state": "installed-family",
            "label": "Version already present",
            "path": model_assets[0].get("path"),
            "index": summary,
        }


def _choose_destination(resolved):
    os.makedirs(resolved["target_dir"], exist_ok=True)
    target_path = os.path.join(resolved["target_dir"], resolved["file_name"])
    if not os.path.exists(target_path):
        return target_path

    try:
        existing_sha = _sha256_file(target_path)
        if resolved.get("sha256") and existing_sha == resolved["sha256"]:
            return target_path
    except OSError:
        pass

    base, extension = os.path.splitext(target_path)
    return f"{base}__v{resolved['version_id']}{extension}"


def _write_sidecars(resolved, model_path, api_key):
    base, _ = os.path.splitext(model_path)
    metadata = {
        "description": re.sub(r"<[^>]+>", "", resolved.get("description") or "").strip(),
        "sd version": resolved.get("base_model") or "Unknown",
        "activation text": ", ".join(resolved.get("trained_words") or []),
        "preferred weight": 1.0,
        "civitai model id": int(resolved["model_id"]),
        "civitai version id": int(resolved["version_id"]),
        "civitai model type": resolved.get("model_type"),
        "civitai file name": resolved.get("file_name"),
        "civitai file sha256": resolved.get("sha256"),
    }
    with open(f"{base}.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=4, ensure_ascii=False)

    images = resolved.get("images") or []
    if not images:
        return
    image_url = images[0].get("url") if isinstance(images[0], dict) else None
    if not image_url:
        return
    try:
        response = requests.get(
            image_url,
            headers={"User-Agent": UI.build_headers(api_key)["User-Agent"]},
            timeout=25,
        )
        if response.status_code == 200:
            with open(f"{base}.png", "wb") as handle:
                handle.write(response.content)
    except (requests.RequestException, OSError):
        pass


def _register_downloaded_asset(resolved, path, sha256):
    try:
        stat = os.stat(path)
    except OSError:
        return
    asset = {
        "path": os.path.abspath(path),
        "name": os.path.basename(path),
        "kind": resolved.get("model_type"),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256,
        "model_id": resolved.get("model_id"),
        "version_id": resolved.get("version_id"),
        "model_name": resolved.get("model_name"),
        "civitai_type": resolved.get("model_type"),
    }
    with INDEX_LOCK:
        LIBRARY.setdefault("assets", {})[asset["path"]] = asset
        _rebuild_lookup_maps()
        _save_index()


def smart_download_target(target, api_key):
    target = parse_target(target)
    if not target:
        return

    source_key = _target_key(target)
    tracker_name = f"ID {target['model_id']}"
    UI.DOWNLOAD_STATUS[tracker_name] = "Resolving model…"

    try:
        if not library_summary()["ready"]:
            UI.DOWNLOAD_STATUS[tracker_name] = "WAIT · Library index is still building"
            _set_state(source_key, state="indexing", label="Indexing library")
            return

        resolved = resolve_target(target, api_key)
        exact_key = f"{resolved['model_id']}:{resolved['version_id']}"
        duplicate = _find_duplicate(resolved)
        if duplicate:
            UI.DOWNLOAD_STATUS.pop(tracker_name, None)
            tracker_name = resolved["model_name"]
            UI.DOWNLOAD_STATUS[tracker_name] = f"DONE · Already installed · {duplicate.get('path')}"
            _set_state(
                source_key,
                state="installed",
                label="Installed",
                path=duplicate.get("path"),
                modelId=resolved["model_id"],
                modelVersionId=resolved["version_id"],
            )
            _set_state(exact_key, **_state_for_key(source_key))
            UI.FAILED_IDS.discard(source_key)
            return

        UI.DOWNLOAD_STATUS.pop(tracker_name, None)
        tracker_name = resolved["model_name"]
        destination = _choose_destination(resolved)
        partial_path = f"{destination}.part"
        _set_state(
            source_key,
            state="queued",
            label="Queued",
            progress=0,
            modelId=resolved["model_id"],
            modelVersionId=resolved["version_id"],
        )

        headers = UI.build_headers(api_key)
        with requests.get(
            resolved["download_url"],
            headers=headers,
            stream=True,
            timeout=900,
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(f"Download HTTP {response.status_code}")

            total_size = int(response.headers.get("content-length", 0) or 0)
            downloaded = 0
            started_at = time.time()

            with open(partial_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    downloaded += len(chunk)
                    elapsed = max(time.time() - started_at, 0.001)
                    speed = (downloaded / (1024 * 1024)) / elapsed
                    if total_size > 0:
                        progress = min((downloaded / total_size) * 100, 100)
                        UI.DOWNLOAD_STATUS[tracker_name] = f"{progress:5.1f}% · {speed:.1f} MB/s"
                    else:
                        progress = None
                        UI.DOWNLOAD_STATUS[tracker_name] = f"{downloaded / (1024 * 1024):.1f} MB · {speed:.1f} MB/s"
                    _set_state(
                        source_key,
                        state="downloading",
                        label="Downloading",
                        progress=progress,
                        speedMBs=round(speed, 1),
                        modelId=resolved["model_id"],
                        modelVersionId=resolved["version_id"],
                    )

        UI.DOWNLOAD_STATUS[tracker_name] = "Verifying SHA-256…"
        _set_state(source_key, state="verifying", label="Verifying")
        downloaded_sha = _sha256_file(partial_path)
        expected_sha = _normalize_sha(resolved.get("sha256"))
        if expected_sha and downloaded_sha != expected_sha:
            raise RuntimeError("SHA-256 mismatch; downloaded file was rejected")

        os.replace(partial_path, destination)
        resolved["sha256"] = expected_sha or downloaded_sha
        _write_sidecars(resolved, destination, api_key)
        _register_downloaded_asset(resolved, destination, resolved["sha256"])

        UI.DOWNLOAD_STATUS[tracker_name] = "DONE · Installed"
        _set_state(
            source_key,
            state="installed",
            label="Installed",
            progress=100,
            path=destination,
            modelId=resolved["model_id"],
            modelVersionId=resolved["version_id"],
        )
        _set_state(
            exact_key,
            state="installed",
            label="Installed",
            progress=100,
            path=destination,
            modelId=resolved["model_id"],
            modelVersionId=resolved["version_id"],
        )
        UI.FAILED_IDS.discard(source_key)
    except Exception as exc:
        try:
            partial_path
        except UnboundLocalError:
            partial_path = None
        if partial_path:
            try:
                if os.path.exists(partial_path):
                    os.remove(partial_path)
            except OSError:
                pass
        UI.DOWNLOAD_STATUS[tracker_name] = f"ERROR · {str(exc)[:120]}"
        UI.FAILED_IDS.add(source_key)
        _set_state(source_key, state="error", label="Download failed", error=str(exc)[:180])


def _smart_worker(target, api_key):
    try:
        smart_download_target(target, api_key)
    finally:
        key = _target_key(parse_target(target) or {})
        with UI.TASK_LOCK:
            UI.ACTIVE_TASKS = max(0, UI.ACTIVE_TASKS - 1)
            UI.PROCESSED_IDS.discard(key)


def smart_start_downloads(targets, threads, force=False):
    normalized = []
    seen = set()
    for raw in targets or []:
        target = parse_target(raw)
        if not target:
            continue
        key = _target_key(target)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(target)

    if not normalized:
        return 0

    if not library_summary()["ready"]:
        UI.DOWNLOAD_STATUS["Library index"] = "WAIT · Building SHA-256 inventory before downloads"
        return 0

    max_workers = max(1, min(int(threads), 10))
    api_key = UI.get_api_key()
    accepted = []

    with UI.TASK_LOCK:
        for target in normalized:
            key = _target_key(target)
            if force or key not in UI.PROCESSED_IDS:
                UI.PROCESSED_IDS.add(key)
                accepted.append(target)
        UI.ACTIVE_TASKS += len(accepted)

    if not accepted:
        return 0

    def run_pool(items):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_smart_worker, target, api_key) for target in items]
            for future in futures:
                try:
                    future.result()
                except Exception:
                    pass

    threading.Thread(target=run_pool, args=(accepted,), daemon=True).start()
    return len(accepted)


def _is_local_request(request):
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost"}


def _require_local(request):
    if not _is_local_request(request):
        raise HTTPException(status_code=403, detail="CivitaiFlow Browser Bridge is local-only")


def register_api(_: object, app: FastAPI):
    @app.get("/civitaiflow/api/health")
    async def civitaiflow_health(request: Request):
        _require_local(request)
        return {"ok": True, "version": "22.5", "library": library_summary()}

    @app.get("/civitaiflow/api/status")
    async def civitaiflow_status(
        request: Request,
        modelId: str,
        modelVersionId: str = None,
    ):
        _require_local(request)
        target = {"model_id": modelId, "version_id": modelVersionId}
        return {"ok": True, **status_for_target(target)}

    @app.post("/civitaiflow/api/capture")
    async def civitaiflow_capture(request: Request, payload: dict = Body(default_factory=dict)):
        _require_local(request)
        target = parse_target(payload.get("url") or payload)
        if not target:
            return {"ok": False, "state": "error", "label": "Invalid Civitai model URL"}

        current = status_for_target(target)
        if current.get("state") == "installed":
            return {"ok": True, **current, "queued": 0}
        if current.get("state") == "indexing":
            return {"ok": False, **current, "queued": 0}

        queued = smart_start_downloads([target], payload.get("threads", 5), force=False)
        if queued:
            _set_state(_target_key(target), state="queued", label="Queued", progress=0)
            return {"ok": True, "state": "queued", "label": "Queued", "queued": queued}
        return {"ok": True, **status_for_target(target), "queued": 0}

    @app.get("/civitaiflow/api/library")
    async def civitaiflow_library(request: Request):
        _require_local(request)
        return {"ok": True, **library_summary()}

    @app.post("/civitaiflow/api/reindex")
    async def civitaiflow_reindex(request: Request):
        _require_local(request)
        started = start_library_index(force=True)
        return {"ok": True, "started": started, "library": library_summary()}


if UI:
    UI.parse_civitai_urls = parse_civitai_targets
    UI.start_downloads = smart_start_downloads

script_callbacks.on_app_started(register_api)
start_library_index(force=True)
