# CivitaiFlow Browser Bridge

The Browser Bridge is an optional Chrome / Edge extension that adds a **Send to Forge** action directly to Civitai model cards and model detail pages.

It exists for one reason: remove the last manual step in the original CivitaiFlow workflow.

Without the bridge:

```text
See model → right-click → Copy link → Sniper capture → download
```

With the bridge:

```text
See model → Send to Forge → Sniper capture → download
```

## Why this is a browser extension

Forge cannot inject controls into the DOM of a cross-origin `https://civitai.com` iframe because the browser's same-origin policy blocks parent-page JavaScript from reading or modifying that document.

A browser content script that is explicitly installed for `https://civitai.com/*` runs inside the Civitai page itself. That lets CivitaiFlow add the button without reverse-proxying Civitai, stripping security headers, copying cookies, or weakening browser security.

The content script is configured with `all_frames: true`, so it can enhance Civitai both:

- when Civitai renders in the Forge iframe; and
- when Civitai is opened in the top-level Companion Window.

## What the button does

The bridge does not download files itself and does not receive your Civitai API token.

When **Send to Forge** is clicked it:

1. resolves the Civitai model URL from the card or current model page;
2. preserves `modelVersionId` when that value exists in the URL;
3. writes that URL to the browser / Windows clipboard;
4. CivitaiFlow's existing Sniper capture sees the URL;
5. Auto download can queue it immediately.

This deliberately reuses the existing capture pipeline instead of creating a second downloader.

## Install in Microsoft Edge

1. Update CivitaiFlow from GitHub first.
2. Open `edge://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked**.
5. Select the `browser-extension` directory from your local CivitaiFlow installation.
6. Reload the CivitaiFlow / Civitai page.

## Install in Google Chrome

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the `browser-extension` directory from your local CivitaiFlow installation.
5. Reload Civitai.

## Expected behavior

On Civitai model cards, hovering the card reveals a small **Send to Forge** control over the preview.

On a model detail page, a persistent **Send to Forge** button appears in the lower-right corner.

After clicking:

- **Sent to Forge** means the URL was successfully placed in the clipboard;
- **Copy failed** means the browser refused clipboard access.

If **Sniper capture** and **Auto download** are enabled in Forge, a successful click should move directly into the normal CivitaiFlow acquisition pipeline.

## Security model

The Browser Bridge requests only:

- access to `https://civitai.com/*`; and
- clipboard write permission.

It does not request access to browser cookies, browsing history, passwords, or arbitrary websites.

It does not read the CivitaiFlow API key from Forge.

## Current limitation

The bridge identifies Civitai cards using model links and DOM heuristics because Civitai's website markup is not a stable public API. If Civitai significantly changes its card structure, the placement heuristic may need an update.

The acquisition backend remains independent of this UI enhancement, so a Civitai markup change cannot break Sniper capture or manual link ingestion.
