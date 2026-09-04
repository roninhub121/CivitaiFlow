# CivitaiFlow Testing

CivitaiFlow crosses four runtime boundaries:

1. Forge/Python compatibility layers;
2. the Forge/Gradio browser UI;
3. the embedded or Companion Civitai browsing surface;
4. the optional CivitaiFlow Browser Bridge content script/service worker.

A release is not considered verified only because Python and JavaScript parse. The syntax gate protects the repository; the local smoke test protects the actual Forge experience.

## Automated release gate

`.github/workflows/validate.yml` checks:

- Python 3.10 compilation for all Forge extension sources;
- JavaScript syntax for the Forge runtime shell, lifecycle UI and Browser Bridge;
- Browser Bridge `manifest.json` JSON validity;
- dependency-light release-contract tests under `tests/`.

22.7.2 specifically guards the regression shown in Forge where the CivitaiFlow logo rendered at page scale while the embedded Civitai iframe stayed near the browser default size.

## Required local 22.7.2 smoke test

### 1. Verify the actual checkout first

From the extension folder:

```powershell
git status --short --branch
git rev-parse --short HEAD
git log -1 --oneline
```

The runtime must be using the checkout you just updated. A stale extension copy elsewhere under Forge can look identical while executing older files.

### 2. Clean Forge restart

- update CivitaiFlow from Git;
- stop Forge completely;
- start Forge again;
- hard-refresh the browser once after Forge is ready;
- open **CivitaiFlow**.

Expected:

- visible release badge: `v22.7.2`;
- compact CivitaiFlow mark, never a page-sized SVG;
- left control rail approximately 340–400 px on desktop;
- embedded Civitai consumes the remaining workspace width;
- iframe height is workstation-sized rather than a default ~300×150 surface;
- **Library & lifecycle** appears as its own runtime card when those widgets are available.

### 3. Runtime-shell ownership

`javascript/civitai_flow.js` is the canonical browser shell in 22.7.2.

This is intentional: that script was already proven to load in the broken Forge runtime because its Companion/Reload toolbar was visible even when nested Gradio CSS was missing. The same proven execution path now owns:

- critical inline logo dimensions;
- critical iframe width/height;
- release badge healing;
- desktop/medium/mobile layout marking;
- premium card and typography styling;
- Companion/Reload toolbar;
- Library & lifecycle host placement.

The separate `javascript/premium_shell.js` compatibility experiment was removed to avoid two self-healing UI loops fighting over the same DOM.

### 4. Responsive shell

Validate at three widths:

- desktop / ultrawide: control rail + browser workspace side-by-side;
- medium: controls reflow while browser remains full-width;
- narrow: one-column stack without horizontal page overflow.

### 5. Embedded browser and Companion fallback

- Confirm **Reload** refreshes the embedded Civitai surface.
- Open **Companion** and confirm Civitai opens as a normal top-level browser window.
- Use Companion for Google/Civitai website authentication when embedded authentication is rejected by browser/OAuth policy.
- Closing Companion should trigger a best-effort embedded reload.

### 6. API authentication

- Open **Get API Key ↗** and confirm it resolves to the current Civitai account page.
- Create/copy a personal API key if needed.
- Paste it into the Forge connection card and click **Connect API**.
- Click **Verify**.

Expected:

```text
Connected as <user>
API authentication active
```

The Browser Bridge must never request, expose, or persist the API key itself.

### 7. Library Intelligence

- Wait for `Library indexing` to transition to an indexed asset count.
- Confirm LoRA and checkpoint counts are plausible.
- Click **Reindex** and confirm a new scan starts without freezing Forge.
- Confirm the library widget stays inside **Library & lifecycle**.

### 8. Existing-model recognition

Choose a Civitai model already present locally.

Expected Browser Bridge state:

```text
Installed
```

Clicking the installed control must not create another model file.

### 9. New-version recognition

Choose a Civitai model for which an older local version exists.

Expected:

```text
Update available
```

Sending it to Forge should preserve the older different file rather than overwrite it blindly.

### 10. New model transfer

Choose a small test LoRA that is not installed.

Expected sequence:

```text
Send to Forge
→ Queued
→ Downloading %
→ Verifying
→ Installed
```

Confirm the final model is not left with a `.part` suffix.

### 11. Resume regression

- Start a sufficiently large transfer.
- Stop Forge while the `.part` file exists.
- Restart Forge.

Expected:

- interrupted queue item becomes resumable;
- CivitaiFlow attempts HTTP Range resume when supported;
- if Range is ignored, that transfer restarts safely;
- SHA-256 verification still occurs before install.

### 12. Hash verification and deduplication

After a successful transfer:

- inspect the JSON sidecar;
- confirm model ID, version ID, model type, source filename and SHA-256;
- re-send the same model;
- confirm CivitaiFlow reports `Installed` without redownloading bytes.

### 13. Type-aware routing

Validate at least:

```text
LoRA       → models/Lora
Checkpoint → models/Stable-diffusion
```

Unsupported model types should fail explicitly instead of silently landing in the LoRA folder.

### 14. Browser Bridge direct mode

Reload `browser-extension/` in Edge/Chrome after an extension update.

Browser Bridge 0.3.0 discovers local Forge ports `7860` through `7863` on both `127.0.0.1` and `localhost`.

- open Civitai;
- confirm model cards show CivitaiFlow state;
- click **Send to Forge**;
- confirm the model queues without a manual clipboard copy.

### 15. Release diagnostic

With Forge running locally, open:

```text
/civitaiflow/api/release
```

Expected contract:

```json
{
  "ok": true,
  "version": "22.7.2",
  "interface": "runtime-shell-v2",
  "runtimeScript": "javascript/civitai_flow.js",
  "browserBridge": "0.3.0"
}
```

This is the quickest way to distinguish a real 22.7.2 runtime from a stale checkout/browser session.

## Release evidence

For a release candidate, capture at minimum:

- Forge startup console with no CivitaiFlow traceback;
- full desktop CivitaiFlow screenshot;
- one narrow/responsive screenshot;
- release diagnostic response;
- library index ready state;
- one Browser Bridge `Installed` or successful transfer state;
- GitHub `validate` workflow success.

## Known CI limitation

GitHub CI does not boot a complete Stable Diffusion WebUI Forge runtime. The Forge callback lifecycle, Gradio composition, actual model directories, Civitai framing behavior and browser-extension injection still require a local smoke test before calling the build runtime-verified.

The repository therefore distinguishes **CI verified** from **Forge runtime verified** instead of presenting syntax success as end-to-end proof.
