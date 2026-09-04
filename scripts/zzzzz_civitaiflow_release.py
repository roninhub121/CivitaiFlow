"""CivitaiFlow final release compatibility contract.

The browser runtime shell now lives in ``javascript/civitai_flow.js`` because
that script is already proven to load on Forge builds where nested Gradio CSS
is ignored. This late Python layer remains as a second safety net for critical
brand/frame dimensions and for a loopback release diagnostic endpoint.
"""

import os

from fastapi import FastAPI, Request
from modules import script_callbacks, script_loading


CIVITAIFLOW_VERSION = "22.7.2"


def _find_module(filename):
    filename = filename.lower()
    for script_path, module in script_loading.loaded_scripts.items():
        if os.path.basename(script_path).lower() == filename:
            return module
    return None


UI = _find_module("ronin_ui.py")
LIB = _find_module("zz_civitaiflow_library.py")
UPD = _find_module("zzz_civitaiflow_updates.py")


if UI:
    UI.CIVITAIFLOW_VERSION = CIVITAIFLOW_VERSION
    UI.CIVITAI_SETTINGS_URL = f"{UI.CIVITAI_BASE_URL}/user/account"

    def build_headers(api_key=None):
        api_key = (api_key if api_key is not None else UI.get_api_key()).strip()
        headers = {
            "User-Agent": f"CivitaiFlow/{CIVITAIFLOW_VERSION} (Stable Diffusion Forge)"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def brand_html():
        return f"""
        <div class="cf-brand" style="display:flex;align-items:center;gap:12px;min-height:48px;overflow:hidden">
            <div class="cf-brand-mark" aria-hidden="true" style="width:36px;height:36px;min-width:36px;max-width:36px;display:grid;place-items:center;overflow:hidden;color:#f97316">
                <svg viewBox="0 0 24 24" fill="none" style="display:block;width:30px;height:30px;min-width:30px;min-height:30px;max-width:30px;max-height:30px">
                    <path d="M7.2 3.8h9.6l4.8 8.2-4.8 8.2H7.2L2.4 12l4.8-8.2Z" stroke="currentColor" stroke-width="1.7"/>
                    <path d="M8.4 8.2h7.2l2.2 3.8-2.2 3.8H8.4L6.2 12l2.2-3.8Z" stroke="currentColor" stroke-width="1.7"/>
                    <circle cx="12" cy="12" r="1.6" fill="currentColor"/>
                </svg>
            </div>
            <div style="min-width:0">
                <div class="cf-brand-row">
                    <span class="cf-brand-name">CivitaiFlow</span>
                    <span class="cf-version">v{CIVITAIFLOW_VERSION}</span>
                </div>
                <div class="cf-brand-sub">Forge-native Civitai workspace · smart acquisition · lifecycle safety</div>
            </div>
        </div>
        """

    def build_civitai_frame(cache_buster=None):
        suffix = f"?cf_reload={cache_buster}" if cache_buster else ""
        return (
            '<div class="cf-frame-shell" '
            'style="position:relative;display:block;width:100%;max-width:none;min-width:0;min-height:640px;height:clamp(640px,calc(100vh - 170px),980px);overflow:hidden">'
            f'<iframe src="{UI.CIVITAI_BASE_URL}/{suffix}" '
            'title="Civitai embedded browser" '
            'referrerpolicy="strict-origin-when-cross-origin" '
            'allow="clipboard-read; clipboard-write; fullscreen" '
            'loading="eager" width="100%" height="100%" '
            'style="display:block;width:100%;max-width:none;height:100%;min-height:640px;border:0"></iframe></div>'
        )

    UI.build_headers = build_headers
    UI.brand_html = brand_html
    UI.build_civitai_frame = build_civitai_frame


if UPD and callable(getattr(UPD, "update_summary", None)):
    _original_update_summary = UPD.update_summary

    def update_summary():
        summary = _original_update_summary()
        summary["version"] = CIVITAIFLOW_VERSION
        return summary

    UPD.update_summary = update_summary


def register_release_api(_: object, app: FastAPI):
    @app.get("/civitaiflow/api/release")
    async def civitaiflow_release(request: Request):
        if LIB and hasattr(LIB, "_require_local"):
            LIB._require_local(request)
        return {
            "ok": True,
            "version": CIVITAIFLOW_VERSION,
            "interface": "runtime-shell-v2",
            "runtimeScript": "javascript/civitai_flow.js",
            "browserBridge": "0.3.0",
        }


script_callbacks.on_app_started(register_release_api)
