# CivitaiFlow

> **See it on Civitai. Send it to Forge. Keep the local library clean.**

CivitaiFlow is a visual Civitai-to-Forge acquisition and local-library layer for **Stable Diffusion WebUI Forge**.

The product keeps the real Civitai browsing experience — previews, creators, versions, examples and model pages — while automating the repetitive work that happens after you decide you want an asset.

```text
Browse visually on Civitai
        ↓
Send to Forge / copy model link
        ↓
Resolve exact model + version
        ↓
Check local SHA-256 inventory
        ↓
Already installed? ── yes → stop, no duplicate
        │
        no
        ↓
Route → download → verify → metadata → register
        ↓
Ready in Forge
        ↓
Future Civitai release?
        ↓
Update Center detects it
```

## Product principles

### Visual discovery stays visual

Civitai itself remains the discovery surface. CivitaiFlow does not try to replace the website with a reduced API gallery.

You can browse through:

- **Embedded Civitai** inside the Forge tab when browser/Civitai framing policy allows it.
- **Companion Window** as a normal top-level browser window for reliable Civitai/Google login and as a fallback when embedding is blocked.

### Acquisition should be one action

The original workflow was:

```text
See model → right-click → Copy link → Sniper → Auto-DL
```

The optional **CivitaiFlow Browser Bridge** reduces that to:

```text
See model → Send to Forge
```

The Browser Bridge adds controls directly to real Civitai cards and model pages.

### The library should know what it already owns

CivitaiFlow indexes local assets by:

- Civitai model ID;
- Civitai `modelVersionId`;
- SHA-256;
- local path;
- asset/model type.

That lets Civitai and Forge expose states such as:

```text
[ Send to Forge ]
[ Installed ]
[ Update available ]
[ Downloading 64% ]
[ Verifying ]
```

### Updates should be safe

A newer checkpoint or LoRA is not automatically a better drop-in replacement for every workflow.

CivitaiFlow 22.6 can detect newer Civitai releases and optionally auto-download them, but automatic updates **keep the previous local version** by default.

No silent destructive replacement.

---

# 22.6 — Model Update Center

22.6 turns the local Library Intelligence index into an update-aware model repository.

The update scanner groups locally indexed files by Civitai model family, checks the latest downloadable version on Civitai, then compares the remote `modelVersionId` and SHA-256 with the local library.

```text
Local model family
      ↓
Civitai latest version
      ↓
latest version/hash already local?
      │
      ├─ yes → CURRENT
      └─ no  → UPDATE AVAILABLE
```

The Forge panel now exposes a compact **Model updates** center:

```text
● Model updates · 14 available
  Notify only · checked 2h ago · every 24h

[ Review ] [ Scan ] [ Update all ]
```

Individual updates show the installed version(s), latest Civitai version and current queue/download state.

## Update modes

Configure them under **Forge → Settings → CivitaiFlow Manager**:

- **Disabled** — no scheduled update checks.
- **Notify only** — default; report newer versions without downloading automatically.
- **Auto-download LoRAs (keep old)** — automatically acquire newer LoRA versions.
- **Auto-download LoRAs + checkpoints (keep old)** — automatically acquire newer LoRAs and checkpoints.

Additional settings control:

- update-check interval;
- update download concurrency;
- maximum automatic updates per scan;
- startup update scan.

Automatic update batches use the same smart acquisition engine as **Send to Forge**:

```text
exact modelVersionId
      ↓
duplicate check
      ↓
type-aware routing
      ↓
*.part transfer
      ↓
SHA-256 verification
      ↓
collision-safe install
      ↓
preview + metadata
      ↓
register in local library
```

Existing versions are kept. If the new version would collide with a different local file, CivitaiFlow uses a `__v<modelVersionId>` suffix instead of overwriting different bytes.

See [Model Updates](docs/UPDATES.md).

---

# 22.5 — Library Intelligence

CivitaiFlow maintains an incremental local inventory in:

```text
<data-dir>/civitai-flow/library-index.json
```

The first scan may need to SHA-256 hash every supported model file. Later scans reuse cached hashes for unchanged files.

For older/manual assets without CivitaiFlow sidecars, known SHA-256 values can be resolved through Civitai's public by-hash API so existing models can still be connected back to Civitai model/version IDs.

## Duplicate prevention

Before a smart transfer starts, CivitaiFlow checks:

1. exact remote SHA-256 against the local index;
2. exact Civitai `modelVersionId` when known;
3. the installed model family for update awareness.

An exact match is not downloaded twice even if the local filename or folder differs.

## Version-aware capture

A URL such as:

```text
https://civitai.com/models/123456?modelVersionId=987654
```

keeps `987654` through resolution and download instead of silently selecting another version.

## Model routing

| Civitai type | Forge location |
| --- | --- |
| LoRA | `models/Lora` |
| Checkpoint | `models/Stable-diffusion` |
| VAE | `models/VAE` |
| Textual Inversion | `<data-dir>/embeddings` |

Unsupported types fail explicitly instead of being silently written into the LoRA directory.

## Integrity verification

Smart downloads are written to `*.part`, hashed, compared with Civitai SHA-256 when supplied, and only then promoted to the final model filename.

See [Library Intelligence](docs/LIBRARY-INTELLIGENCE.md).

---

# Browser Bridge

The optional Manifest V3 Browser Bridge lives in [`browser-extension/`](browser-extension/).

It enhances the real Civitai website instead of recreating it.

When Forge is reachable locally:

```text
Civitai card
    ↓
Browser Bridge
    ↓
127.0.0.1:7860/civitaiflow/api/*
    ↓
CivitaiFlow smart acquisition
```

The bridge can show live local status while you browse:

```text
Send to Forge
Installed
Update available
Queued
Downloading 64%
Verifying
```

If the local bridge cannot be reached, it falls back to copying the canonical Civitai URL so the original Windows Sniper workflow can continue.

The Browser Bridge never receives the Civitai API key.

## Install in Edge

1. Update CivitaiFlow and restart Forge.
2. Open `edge://extensions`.
3. Enable **Developer mode**.
4. Choose **Load unpacked** (or **Reload** if it is already installed).
5. Select the local `CivitaiFlow/browser-extension` folder.
6. Reload Civitai / the CivitaiFlow tab.

Chrome uses the same process from `chrome://extensions`.

See [Browser Bridge documentation](browser-extension/README.md).

---

# Authentication

CivitaiFlow interacts with two separate authentication systems.

## Website session

The Civitai website uses normal browser cookies and Civitai/Google login.

Google OAuth can reject authentication inside embedded user-agents/iframes, and browser privacy rules can isolate third-party cookies.

Use **Open Companion Window** when login inside the embedded view fails.

## Civitai API credential

The Python backend uses the configured Civitai API key for authenticated metadata and gated downloads:

```http
Authorization: Bearer <CIVITAI_API_KEY>
```

The API key does not create a website cookie and cannot log the Civitai iframe into the website.

See [Authentication](docs/AUTHENTICATION.md).

---

# Core features

- Real Civitai website as the visual discovery experience.
- Embedded mode plus Companion Window fallback.
- Optional one-click Browser Bridge on Civitai cards/pages.
- Live installed/update/download states while browsing.
- Windows clipboard Sniper fallback.
- Civitai API-key verification and Bearer authentication.
- Version-aware `modelVersionId` resolution.
- Incremental local SHA-256 model inventory.
- Duplicate prevention across indexed model repositories.
- LoRA/checkpoint/VAE/Textual-Inversion routing.
- Concurrent background downloads.
- `*.part` temporary transfers.
- SHA-256 verification before final rename.
- Collision-safe multi-version storage.
- Preview-image and Forge metadata generation.
- Scheduled update discovery.
- Manual per-model and **Update all** workflows.
- Optional safe auto-download of newer LoRAs/checkpoints while keeping older versions.
- Retry handling and live transfer telemetry.

---

# Quick start

1. Install through **Forge → Extensions → Install from URL**:

   `https://github.com/roninhub121/CivitaiFlow`

2. Apply changes and restart Forge.
3. Open **CivitaiFlow**.
4. Configure a Civitai API key when authenticated/gated access is needed.
5. Let **Library Intelligence** finish the initial index.
6. Keep **Sniper capture** and **Auto download** enabled if you want clipboard fallback.
7. Optionally load the Browser Bridge for one-click Civitai controls.
8. Browse visually and send models to Forge.
9. Use **Model updates** to review newer releases or configure a safe auto-update policy in Settings.

---

# Local API

CivitaiFlow exposes loopback-only endpoints for the Browser Bridge and Forge UI:

```text
GET  /civitaiflow/api/health
GET  /civitaiflow/api/status
POST /civitaiflow/api/capture
GET  /civitaiflow/api/library
POST /civitaiflow/api/reindex

GET  /civitaiflow/api/updates
POST /civitaiflow/api/updates/scan
POST /civitaiflow/api/updates/apply
POST /civitaiflow/api/updates/apply-all
```

These endpoints reject non-loopback clients. Running Forge with `--listen` does not intentionally turn CivitaiFlow into an unauthenticated LAN model-download/update service.

---

# Current limitations

- Embedded Civitai remains dependent on Civitai/browser framing policy.
- The Browser Bridge currently assumes local Forge on the default port `7860`.
- Initial SHA-256 indexing can be disk-intensive for very large existing libraries.
- Civitai card placement uses DOM heuristics and can require maintenance after a Civitai frontend redesign.
- Sniper capture is Windows/PowerShell-specific.
- Automatic updates currently keep old versions; archive/replace policies are not implemented yet.
- There is no per-model update pin/ignore list yet.
- Large checkpoint update batches do not yet estimate required free disk space.
- The download queue does not yet persist/resume across Forge restarts.
- Forge model inventories are not yet automatically refreshed after every successful install/update.
- API keys are stored through Forge configuration rather than DPAPI/Credential Manager.
- The Python core still uses compatibility layers around the original monolithic UI script and should be modularized in a future major release.

---

# Recommended roadmap

1. **Forge refresh after install/update** — make newly acquired LoRAs/checkpoints immediately visible without manual refresh.
2. **Persistent/resumable queue** — survive Forge restarts and resume large checkpoint downloads.
3. **Per-model update pinning** — ignore/pin specific versions or model families.
4. **Disk-space estimation** — especially before **Update all** and automatic checkpoint batches.
5. **Update history + rollback helpers** — show what changed and make switching versions easier.
6. **Archive/replace policy** — explicit opt-in alternatives to the default KEEP BOTH behavior.
7. **Library Health** — duplicates, missing previews, orphan sidecars, stale entries and repair actions.
8. **User-defined storage rules** — organize by type/base model/creator/custom templates.
9. **Browser Bridge configuration** — explicit Forge URL/port and local bridge token for advanced setups.
10. **Secure credential storage** — optional Windows DPAPI/Credential Manager.
11. **Official Civitai OAuth + PKCE** — once CivitaiFlow has its own registered OAuth client.
12. **Modular Python core** — split client, resolver, index, updates, queue, storage and metadata into dedicated modules.

See [Architecture](docs/ARCHITECTURE.md) for the deeper engineering direction.

---

# Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Authentication](docs/AUTHENTICATION.md)
- [Library Intelligence](docs/LIBRARY-INTELLIGENCE.md)
- [Model Updates](docs/UPDATES.md)
- [Browser Bridge](browser-extension/README.md)
- [Testing](docs/TESTING.md)
- [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).

## Credits

Developed and maintained by **Ronin**.

Built for the Stable Diffusion WebUI Forge workflow.
