# CivitaiFlow Testing

CivitaiFlow crosses four runtime boundaries:

1. Forge/Python compatibility layers;
2. the Forge/Gradio browser UI;
3. the embedded or Companion Civitai browsing surface;
4. the optional CivitaiFlow Browser Bridge content script/service worker.

A release is not considered verified only because Python and JavaScript parse. The syntax gate protects the repository; the local smoke test protects the actual Forge experience.

## Automated release gate

`.github/workflows/validate.yml` checks:

- Python 3.10 compilation for all Forge extension sources, including the release compatibility layer;
- JavaScript syntax for all Forge-side and Browser Bridge scripts, including the premium shell;
- Browser Bridge `manifest.json` JSON validity;
- dependency-light release-contract tests under `tests/`.

The release-contract suite specifically guards the failures that caused the 22.7.1 stabilization work: stale version badges, missing critical iframe/logo sizing, obsolete Civitai account routing, and Browser Bridge port assumptions.

## Required local 22.7.1 smoke test

### 1. Clean Forge restart

- Update CivitaiFlow from Git.
- Stop Forge completely; do not rely on a tab refresh alone.
- Start Forge again.
- Hard-refresh the browser once after Forge is ready.
- Open **CivitaiFlow**.

Expected:

- visible release badge: `v22.7.1`;
- compact CivitaiFlow mark, never a page-sized SVG;
- left control rail approximately 340–410 px on desktop;
- embedded Civitai workspace consumes the remaining width;
- iframe height is workstation-sized rather than the browser default ~300×150 surface;
- **Library & lifecycle** appears as its own runtime card when those widgets are available.

### 2. Responsive shell

Validate at three useful widths:

- desktop / ultrawide: sidebar + browser workspace side-by-side;
- medium window: controls can reflow while the browser remains full-width;
- narrow window: one-column stack without horizontal page overflow.

The premium shell is deliberately injected from `javascript/premium_shell.js` because some Forge/Gradio combinations ignore CSS supplied by nested `gr.Blocks(css=...)`. Critical logo and iframe dimensions also have a Python-side inline fallback in the final release layer.

### 3. Embedded browser and Companion fallback

- Confirm **Reload** refreshes the embedded Civitai surface.
- Open **Companion** and confirm Civitai opens as a normal top-level browser window.
- Use Companion for Google/Civitai website authentication when embedded authentication is rejected by browser/OAuth policy.
- Closing the Companion window should trigger a best-effort embedded reload.

### 4. API authentication

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

### 5. First library index

- Wait for `Library indexing` to transition to an indexed asset count.
- Confirm LoRA and checkpoint counts are plausible.
- Click **Reindex** and confirm a new scan starts without freezing Forge.
- Confirm the library widget stays inside **Library & lifecycle**, not inside the API credential controls.

### 6. Existing-model recognition

Choose a Civitai model that is already present locally.

Expected Browser Bridge state:

```text
Installed
```

Clicking the installed control must not create another model file.

### 7. New-version recognition

Choose a Civitai model for which an older local version exists.

Expected state when the remote/current target differs:

```text
Update available
```

Sending it to Forge should preserve the older different file rather than overwrite it blindly.

### 8. New model transfer

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

### 9. Resume regression

- Start a sufficiently large model transfer.
- Stop Forge while the `.part` file exists.
- Restart Forge.

Expected:

- the interrupted queue item becomes resumable;
- CivitaiFlow attempts HTTP Range resume when supported;
- if the server does not honor Range, that transfer restarts safely rather than appending incompatible bytes;
- SHA-256 verification still occurs before install.

### 10. Hash verification and deduplication

After a successful transfer:

- inspect the generated JSON sidecar;
- confirm Civitai model ID, version ID, model type, source filename and SHA-256 are recorded;
- re-send the same model;
- confirm CivitaiFlow returns `Installed` without downloading the bytes again.

### 11. Type-aware routing

Validate at least LoRA and checkpoint routing when practical:

```text
LoRA       → models/Lora
Checkpoint → models/Stable-diffusion
```

Unsupported model types should fail explicitly instead of silently landing in the LoRA folder.

### 12. Browser Bridge direct mode

Reload `browser-extension/` in Edge/Chrome after an extension update.

CivitaiFlow Browser Bridge 0.3.0 discovers common local Forge ports `7860` through `7863` on both `127.0.0.1` and `localhost`.

- open Civitai;
- confirm model cards show CivitaiFlow state;
- click **Send to Forge**;
- confirm the model queues without a manual clipboard copy;
- if Forge uses one of the supported ports, the bridge should remember the working base for later requests.

### 13. Sniper fallback

Stop Forge or otherwise make the loopback bridge unavailable, then click **Send to Forge** on Civitai.

The Browser Bridge should fall back to clipboard capture. After Forge is available again, the original Sniper/manual workflow must remain usable.

## Release evidence

For a release candidate, capture at minimum:

- Forge startup console with no CivitaiFlow traceback;
- full CivitaiFlow desktop tab screenshot;
- one responsive/narrow screenshot;
- API Verify success or a deliberate unauthenticated-state screenshot;
- library index ready state;
- one Browser Bridge `Installed` or successful transfer state;
- GitHub `validate` workflow success.

## Known CI limitation

GitHub CI does not boot a complete Stable Diffusion WebUI Forge runtime. The Forge callback lifecycle, Gradio composition, actual model directories, Civitai framing behavior and browser-extension injection still require a local smoke test before calling the build runtime-verified.

The repository therefore distinguishes **CI verified** from **Forge runtime verified** instead of presenting syntax success as end-to-end proof.
