# CivitaiFlow Browser Bridge

The Browser Bridge is an optional Chrome / Edge extension that turns Civitai model cards into a one-click front end for the local CivitaiFlow service running in Stable Diffusion WebUI Forge.

Its goal is the shortest useful workflow possible:

```text
See model → Send to Forge → duplicate check → download/verify → ready locally
```

No right-click and no manual copy/paste are required when the local Forge bridge is reachable.

## What appears on Civitai

The content script enhances Civitai model cards and model detail pages with a compact action/state control.

Possible states include:

```text
Send to Forge
Installed
Update available
Queued
Downloading 64%
Verifying
Indexing library
```

This means Civitai becomes a visual catalog for both remote discovery and local-library awareness: while browsing, you can see whether the target is already present in Forge.

## Why this is a browser extension

Forge cannot inject controls into the DOM of a cross-origin `https://civitai.com` iframe because the browser same-origin policy blocks parent-page JavaScript from reading or modifying that document.

A content script explicitly installed for Civitai runs in the Civitai page itself and can add the controls without proxying Civitai, copying cookies, stripping security headers, or weakening browser security.

The content script uses `all_frames: true`, so it can enhance Civitai both:

- when Civitai successfully renders inside the Forge iframe; and
- when Civitai is opened in the top-level CivitaiFlow Companion Window.

## Direct local bridge

Version 0.2 prefers a direct local connection instead of using the clipboard as the primary transport.

```text
Civitai content script
        ↓
Browser Bridge service worker
        ↓
127.0.0.1:7860 / localhost:7860
        ↓
CivitaiFlow Forge API
        ↓
Smart resolver + library index + download manager
```

The service worker talks only to the local CivitaiFlow endpoints exposed by Forge.

The Python backend remains responsible for:

- Civitai API authentication;
- version resolution;
- duplicate detection;
- download routing;
- SHA-256 verification;
- local file writes.

The browser extension does **not** receive your Civitai API token.

## Clipboard / Sniper fallback

The original Sniper workflow remains a fallback.

If the local Forge service cannot be reached, **Send to Forge** writes the canonical Civitai model URL to the clipboard. Sniper capture can then process it exactly as before.

So the extension degrades from:

```text
one-click direct bridge
```

to:

```text
one-click clipboard bridge → Sniper
```

rather than becoming unusable.

## Version preservation

If a Civitai URL contains a version selector, the Browser Bridge preserves it:

```text
https://civitai.com/models/123456?modelVersionId=987654
```

The Forge smart resolver uses that `modelVersionId` instead of silently choosing another version.

## Local-library states

### Installed

The exact target is already in the indexed Forge library. The control remains visible and no second download is started.

### Update available

CivitaiFlow recognizes the model family locally, but the current/requested Civitai version is different.

Clicking the control queues the newer/current target while preserving the existing file unless it is byte-identical.

### Downloading

The control polls the local Forge service and displays live transfer progress.

### Indexing library

On first startup CivitaiFlow builds a SHA-256 inventory of supported Forge model folders. Smart downloads are held until that initial inventory is ready so duplicate protection is not bypassed during startup.

## Install in Microsoft Edge

1. Update the CivitaiFlow Forge extension from GitHub.
2. Restart Forge.
3. Open `edge://extensions`.
4. Enable **Developer mode**.
5. If Browser Bridge was already loaded, click **Reload** on the extension card. Otherwise click **Load unpacked**.
6. Select the `browser-extension` directory from the local CivitaiFlow installation.
7. Reload Civitai / the CivitaiFlow tab.

## Install in Google Chrome

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Reload the existing Browser Bridge or click **Load unpacked**.
4. Select the `browser-extension` directory from the local CivitaiFlow installation.
5. Reload Civitai.

## Permissions

The Manifest V3 extension requests:

- `https://civitai.com/*` so it can enhance Civitai pages;
- `http://127.0.0.1/*` and `http://localhost/*` so its background service worker can talk to local Forge;
- `clipboardWrite` only for the Sniper fallback path.

It does not request browser history, password, cookie, or all-sites permissions.

## Local-only security boundary

The Forge Browser Bridge API rejects non-loopback clients.

This is intentional. If Forge is launched with `--listen`, CivitaiFlow should not automatically expose a remote model-download control surface to the LAN.

The current Browser Bridge therefore targets a local Forge session on the default `7860` port.

A future release can add an explicit, opt-in configurable Forge URL with an authentication token for advanced remote setups.

## DOM resilience

Civitai does not expose a stable public DOM contract for model cards. The Browser Bridge identifies cards through Civitai model links plus bounded layout heuristics.

If Civitai significantly changes its frontend markup, the button-placement heuristic may need to be updated. The Forge acquisition backend, local library index, and manual/Sniper capture remain independent from that DOM layer.

## Related documentation

- [Main README](../README.md)
- [Library Intelligence](../docs/LIBRARY-INTELLIGENCE.md)
- [Architecture](../docs/ARCHITECTURE.md)
- [Authentication](../docs/AUTHENTICATION.md)
