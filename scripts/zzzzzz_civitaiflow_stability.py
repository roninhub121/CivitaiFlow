"""Late-loaded 22.8 stability hotfixes for Forge/Windows.

This layer deliberately avoids another permanent DOM or backend polling loop. It:

- replaces the PowerShell clipboard subprocess with Win32 clipboard access;
- keeps Sniper capture cheap and observable;
- starts in a safe workspace without loading the cross-origin Civitai iframe;
- keeps the iframe available only through the existing Reload Panel action;
- re-declares the API-key settings control as a password field.

The module is intentionally loaded after the release compatibility layer.
"""

import ctypes
import html
import os
import time
from ctypes import wintypes

import gradio as gr
from modules import script_callbacks, script_loading, shared


CF_UNICODETEXT = 13
_CAPTURE_NOTE = ""
_CAPTURE_NOTE_AT = 0.0
_LAST_CLIPBOARD_SEQUENCE = None


def _find_module(filename):
    filename = filename.lower()
    for script_path, module in script_loading.loaded_scripts.items():
        if os.path.basename(script_path).lower() == filename:
            return module
    return None


UI = _find_module("ronin_ui.py")


def on_ui_settings():
    """Override the legacy plaintext settings widget with a password textbox.

    Forge executes on_ui_settings callbacks in registration order. Re-registering
    the same option key late keeps the stored value but replaces the UI metadata.
    """

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


def _sanitize_clipboard_text(value):
    text = str(value or "").strip()
    if not text or len(text) > 4096:
        return ""
    if "$uiCode" in text or "import os" in text:
        return ""
    return text


def _native_windows_clipboard():
    """Return new Windows Unicode clipboard text without spawning PowerShell.

    GetClipboardSequenceNumber lets the 1.5 s Gradio timer perform an almost-free
    check when the clipboard has not changed. The old implementation launched a
    full PowerShell process every tick, which was unnecessarily expensive and a
    plausible contributor to long-running Forge UI stalls.
    """

    global _LAST_CLIPBOARD_SEQUENCE

    if os.name != "nt":
        return ""

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
        sequence = int(user32.GetClipboardSequenceNumber() or 0)
        if sequence and sequence == _LAST_CLIPBOARD_SEQUENCE:
            return ""
        if sequence:
            _LAST_CLIPBOARD_SEQUENCE = sequence

        user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""

        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        if not user32.OpenClipboard(None):
            return ""

        try:
            user32.GetClipboardData.argtypes = [wintypes.UINT]
            user32.GetClipboardData.restype = wintypes.HANDLE
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""

            kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                return ""
            try:
                return _sanitize_clipboard_text(ctypes.wstring_at(pointer))
            finally:
                kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    except Exception:
        return ""


def _safe_workspace_html(_cache_buster=None):
    return """
    <div class="cf-frame-shell cf-safe-workspace" data-cf-workspace="safe">
      <div class="cf-safe-workspace-inner">
        <div class="cf-safe-kicker">STABILITY MODE</div>
        <h2>Civitai browsing is separated from Forge rendering</h2>
        <p>
          The embedded Civitai website is disabled on startup because the remote,
          cross-origin page can become heavy, show ads, lose website-session state,
          or stall the Forge tab. Your API downloads and local library continue to work.
        </p>
        <div class="cf-safe-grid">
          <div>
            <strong>Recommended</strong>
            <span>Use <b>Companion</b> to browse Civitai normally, then use Send now / Sniper in Forge.</span>
          </div>
          <div>
            <strong>Optional</strong>
            <span><b>Reload Panel</b> loads the embedded Civitai site for this session only.</span>
          </div>
        </div>
        <div class="cf-safe-note">No remote Civitai page is running inside Forge until you explicitly load it.</div>
      </div>
    </div>
    """


def _embedded_workspace_html(cache_buster=None):
    if not UI:
        return ""
    suffix = f"?cf_reload={cache_buster}" if cache_buster else ""
    return (
        '<div class="cf-frame-shell" data-cf-workspace="embedded" '
        'style="position:relative;display:block;width:100%;max-width:none;min-width:0;min-height:640px;height:clamp(640px,calc(100vh - 170px),980px);overflow:hidden">'
        f'<iframe src="{UI.CIVITAI_BASE_URL}/{suffix}" '
        'title="Civitai embedded browser" '
        'referrerpolicy="strict-origin-when-cross-origin" '
        'allow="clipboard-read; clipboard-write; fullscreen" '
        'loading="lazy" width="100%" height="100%" '
        'style="display:block;width:100%;max-width:none;height:100%;min-height:640px;border:0"></iframe></div>'
    )


def _set_capture_note(message):
    global _CAPTURE_NOTE, _CAPTURE_NOTE_AT
    _CAPTURE_NOTE = str(message or "")
    _CAPTURE_NOTE_AT = time.time()


def _activity_text():
    lines = []
    if UI.ACTIVE_TASKS > 0:
        lines.append(f"ACTIVE DOWNLOADS  {UI.ACTIVE_TASKS}\n" + "─" * 34)
    lines.extend(
        [f"{name[:36]}\n  {status}\n" for name, status in UI.DOWNLOAD_STATUS.items()]
    )
    if _CAPTURE_NOTE and time.time() - _CAPTURE_NOTE_AT < 8:
        lines.insert(0, f"SNIPER\n  {_CAPTURE_NOTE}\n")
    return "\n".join(lines)


def _master_tick(current_text, is_sniper, is_auto, threads):
    """Cheap clipboard capture + existing queue/status maintenance."""

    current_text = current_text or ""
    text_update = gr.update()

    if is_sniper:
        clip = _native_windows_clipboard()
        if clip:
            try:
                targets = UI.parse_civitai_urls(clip)
            except Exception:
                targets = []

            if targets:
                UI.LAST_CLIPBOARD = clip
                if is_auto:
                    queued = UI.start_downloads(targets, threads)
                    if queued:
                        _set_capture_note(f"Clipboard link recognized · {queued} queued")
                    else:
                        _set_capture_note("Clipboard link recognized · already queued/installed or library still indexing")
                else:
                    if clip not in current_text:
                        current_text = f"{current_text.strip()}\n{clip}".strip()
                        text_update = current_text
                    _set_capture_note("Clipboard link recognized · waiting for manual send")

    if is_auto and current_text.strip():
        try:
            targets = UI.parse_civitai_urls(current_text)
        except Exception:
            targets = []
        if targets:
            queued = UI.start_downloads(targets, threads)
            if queued:
                text_update = ""
                _set_capture_note(f"Text link recognized · {queued} queued")

    now = time.time()
    for name, status in list(UI.DOWNLOAD_STATUS.items()):
        is_error = str(status).startswith("ERROR")
        ttl = 60 if is_error else 8
        if str(status).startswith("DONE") or is_error:
            if name not in UI.EXPIRATION_REGISTRY:
                UI.EXPIRATION_REGISTRY[name] = now
            elif now - UI.EXPIRATION_REGISTRY[name] > ttl:
                UI.DOWNLOAD_STATUS.pop(name, None)
                UI.EXPIRATION_REGISTRY.pop(name, None)

    activity = _activity_text()
    if activity:
        return text_update, activity
    return text_update, "IDLE\nCopy a Civitai model link or paste one and use Send now."


def _compact_connection_help():
    return """
    <div class="cf-help">
      <strong>API key = downloads, not website login.</strong>
      The key authenticates metadata and gated downloads. Civitai website login stays in the browser/Companion session.
    </div>
    """


if UI:
    # These names are resolved from ronin_ui.py globals when its registered
    # on_ui_tabs callback finally executes, so late assignment is sufficient.
    UI.get_windows_clipboard = _native_windows_clipboard
    UI.master_tick = _master_tick
    UI.build_civitai_frame = _safe_workspace_html
    UI.reload_civitai_frame = lambda: _embedded_workspace_html(int(time.time()))
    UI.connection_help_html = _compact_connection_help
