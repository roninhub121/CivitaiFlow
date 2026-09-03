# CivitaiFlow

> **See it on Civitai. Send it to Forge. Keep the local library clean.**

CivitaiFlow is a visual Civitai-to-Forge acquisition bridge for **Stable Diffusion WebUI Forge**.

The product goal is deliberately simple: keep the real Civitai discovery experience — previews, creators, versions, examples and model pages — while removing the repetitive work between finding an asset and having it ready locally.

```text
Browse visually on Civitai
        ↓
Send to Forge / copy model link
        ↓
Resolve exact model + version
        ↓
Check the local SHA-256 library index
        ↓
Already installed? ── yes → stop, no duplicate
        │
        no
        ↓
Route → download → verify → metadata → register
        ↓
Ready in Forge
```

## Why CivitaiFlow exists

Downloading models is easy. Maintaining a large local model library without constant context switching, wrong versions, duplicate files and manual cleanup is not.

CivitaiFlow is designed around three product principles:

### 1. Visual discovery stays visual

The Civitai website remains the discovery surface. You can inspect preview images, model pages, versions, creators and other context before deciding what belongs in your local library.

CivitaiFlow supports two website surfaces:

- **Embedded Civitai** inside the Forge tab when browser/Civitai framing policy allows it.
- **Companion Window** as a normal top-level browser window for reliable Google/Civitai login and as a fallback when embedding is blocked.

### 2. Acquisition should be one action

The original workflow was:

```text
See model → right-click → Copy link → Sniper → Auto-DL
```

The optional **CivitaiFlow Browser Bridge** reduces that to:

```text
See model → Send to Forge
```

The button is added directly to Civitai model cards and model detail pages.

### 3. The library should know what it already owns

CivitaiFlow 22.5 adds a persistent local inventory built around:

- Civitai model ID;
- Civitai `modelVersionId`;
- SHA-256;
- local path and model type.

This lets Civitai cards expose useful local state while you browse:

```text
[ Send to Forge ]
[ Installed ]
[ Update available ]
[ Downloading 64% ]
[ Verifying ]
[ Indexing library ]
```

## 22.5 — Library Intelligence

22.5 moves duplicate prevention from a filename check to an actual asset inventory.

### Smart local index

On Forge startup, CivitaiFlow scans supported model locations and creates an incremental SHA-256 index in:

```text
<data-dir>/civitai-flow/library-index.json
```

The first scan may take time on a large checkpoint library because every previously unknown file must be hashed once. Future scans reuse cached hashes for files whose path, size and modification time have not changed.

The Forge CivitaiFlow panel exposes the index state and a **Reindex** action.

### Duplicate prevention

Before a smart transfer starts, CivitaiFlow checks:

1. exact remote SHA-256 against the local index;
2. exact Civitai model version when known from sidecar metadata;
3. the locally indexed model family for update detection.

If the exact file is already installed, no model bytes are downloaded again.

### Existing/manual library recognition

CivitaiFlow reads its own JSON sidecars when available. For files without sidecar IDs, the indexer can resolve SHA-256 values through Civitai's public batch by-hash API, which allows many older/manual files to be identified without relying on filenames.

### Version-aware capture

A URL such as:

```text
https://civitai.com/models/123456?modelVersionId=987654
```

keeps `987654` all the way into the resolver. CivitaiFlow no longer intentionally discards that version selector in the smart acquisition path.

### Model routing

The smart storage router recognizes:

| Civitai type | Forge location |
| --- | --- |
| LoRA | `models/Lora` |
| Checkpoint | `models/Stable-diffusion` |
| VAE | `models/VAE` |
| Textual Inversion | `<data-dir>/embeddings` |

The primary product focus remains LoRAs and checkpoints. Unsupported Civitai resource types fail explicitly rather than silently landing in the LoRA directory.

### Integrity verification

Smart downloads are written to `*.part`, hashed, compared with Civitai SHA-256 when supplied, and only then promoted to the final model filename.

A corrupted/mismatched transfer is rejected instead of being presented to Forge as a valid model.

See [Library Intelligence](docs/LIBRARY-INTELLIGENCE.md) for the complete design.

## Browser Bridge

The optional Manifest V3 Browser Bridge lives in [`browser-extension/`](browser-extension/).

It enhances the real Civitai website rather than recreating a partial API browser.

### Direct mode

When local Forge is reachable on port `7860`:

```text
Civitai card
    ↓
Browser Bridge background service worker
    ↓
127.0.0.1:7860/civitaiflow/api/*
    ↓
CivitaiFlow smart acquisition
```

The Browser Bridge can query local status and send a model directly to Forge without using the clipboard.

### Sniper fallback

If the local service cannot be reached, the Browser Bridge falls back to copying the canonical model URL. The existing Windows Sniper capture then continues the original workflow.

The Browser Bridge never receives the Civitai API key.

### Install the Browser Bridge in Edge

1. Update CivitaiFlow and restart Forge.
2. Open `edge://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked** (or **Reload** if already installed).
5. Select the local `CivitaiFlow/browser-extension` directory.
6. Reload Civitai / the CivitaiFlow tab.

Chrome uses the same process from `chrome://extensions`.

See [Browser Bridge documentation](browser-extension/README.md).

## Website authentication vs API authentication

CivitaiFlow interacts with two separate authentication systems.

### Website session

The actual Civitai website uses browser cookies and the normal Civitai/Google login flow.

Google OAuth can reject authorization inside embedded user-agents/iframes. Also, Civitai and the browser control framing and third-party-cookie policy.

Use **Open Companion Window** when login inside the iframe fails.

### API credential

CivitaiFlow's Python backend uses the configured Civitai API key for authenticated metadata and gated downloads:

```http
Authorization: Bearer <CIVITAI_API_KEY>
```

The API key does not create a Civitai website cookie and cannot log the iframe into the website.

Use the **Civitai connection** card in Forge to:

- paste/connect an API key;
- validate it through `/api/v1/me`;
- verify the saved key;
- open the Civitai account page;
- disconnect/remove the saved key.

See [Authentication](docs/AUTHENTICATION.md).

## Embedded Civitai and Companion Window

CivitaiFlow intentionally keeps the embedded Civitai experience because visual browsing is central to the product.

However, a remote website is not a stable iframe API. Civitai can control embedding through CSP / `X-Frame-Options`, while browser privacy rules can isolate cookies in a cross-site frame.

The resilient discovery model is therefore:

```text
Embedded Civitai      → preferred integrated visual surface when available
Companion Window      → top-level Civitai surface for login/fallback
Browser Bridge        → one-click controls and local-library state
Forge backend         → resolution, auth, dedup, transfer, verification, storage
```

CivitaiFlow does not attempt to bypass these security boundaries by scraping cookies, stripping remote security headers, or turning API tokens into website session cookies.

## Core features

- Real Civitai website as the visual discovery experience.
- Embedded mode plus top-level Companion Window fallback.
- Optional one-click Browser Bridge on Civitai cards/pages.
- Live `Installed / Update available / Downloading` states while browsing.
- Windows clipboard Sniper capture retained as a fallback/manual workflow.
- Civitai API key verification and Bearer-authenticated requests.
- Version-aware smart resolution using `modelVersionId`.
- Incremental local SHA-256 model inventory.
- Duplicate prevention across indexed model locations.
- LoRA/checkpoint/VAE/Textual-Inversion routing.
- Real concurrent downloads.
- `*.part` temporary transfers.
- SHA-256 verification before final rename.
- Collision-safe version suffixes instead of blind overwrite.
- Civitai preview-image download.
- Forge JSON metadata with Civitai IDs, activation words, base model, type, filename and SHA-256.
- Retry handling and live transfer telemetry.

## Quick start

1. Install through **Forge → Extensions → Install from URL**:

   `https://github.com/roninhub121/CivitaiFlow`

2. Apply/restart Forge.
3. Open **CivitaiFlow**.
4. Configure a Civitai API key in the connection card if you need authenticated/gated access.
5. Let the local library index reach **ready**.
6. Keep **Sniper capture** and **Auto download** enabled if you want the legacy/manual capture path.
7. Optionally load the Browser Bridge for one-click controls.
8. Browse Civitai visually and send models to Forge.

## Runtime local API

22.5 exposes a loopback-only service used by the Browser Bridge:

```text
GET  /civitaiflow/api/health
GET  /civitaiflow/api/status
POST /civitaiflow/api/capture
GET  /civitaiflow/api/library
POST /civitaiflow/api/reindex
```

The endpoints reject non-loopback clients. Running Forge with `--listen` does not intentionally turn CivitaiFlow into an unauthenticated LAN download service.

## Current limitations

- Embedded Civitai remains dependent on Civitai/browser framing policy.
- The Browser Bridge currently assumes local Forge on the default port `7860`.
- Initial SHA-256 indexing can be disk-intensive for very large existing libraries.
- Civitai card placement uses DOM heuristics and may require maintenance when Civitai redesigns its frontend.
- Sniper capture is Windows/PowerShell-specific.
- Browser Bridge remote-Forge support is intentionally not enabled yet.
- The original `ronin_ui.py` is still larger/more coupled than the long-term target architecture.
- API keys are stored through Forge configuration; CivitaiFlow does not yet provide DPAPI/Credential Manager secret storage.

## Recommended roadmap

The next development priorities are:

1. **Forge refresh after install** — refresh LoRA/checkpoint inventories automatically after a successful transfer.
2. **Persistent queue** — survive Forge restarts and resume interrupted downloads safely.
3. **Update policy** — choose keep-old / replace / archive when a new model version exists.
4. **Library repair view** — report missing previews, orphan sidecars, stale index entries and known duplicates.
5. **User-defined storage rules** — organize by type, base model, creator or custom category instead of remote first-tag routing.
6. **Browser Bridge configuration** — explicit Forge URL/port plus a local bridge token for advanced non-default setups.
7. **Secure credential storage** — optional Windows DPAPI/Credential Manager.
8. **Official Civitai OAuth + PKCE** — once CivitaiFlow has its own registered OAuth client.
9. **Modular Python core** — split Civitai client, resolver, index, queue, storage and metadata from the Gradio composition layer.

See [Architecture](docs/ARCHITECTURE.md) for the deeper engineering direction.

## Repository documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Authentication](docs/AUTHENTICATION.md)
- [Library Intelligence](docs/LIBRARY-INTELLIGENCE.md)
- [Browser Bridge](browser-extension/README.md)
- [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).

## Credits

Developed and maintained by **Ronin**.

Built for the Stable Diffusion WebUI Forge workflow.
