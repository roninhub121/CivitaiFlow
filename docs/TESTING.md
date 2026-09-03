# CivitaiFlow Testing

CivitaiFlow spans three different runtime boundaries:

1. Forge/Python;
2. the Forge browser UI;
3. the optional Civitai Browser Bridge content script/service worker.

A release should therefore be validated at both syntax and runtime levels.

## Automated syntax gate

`.github/workflows/validate.yml` checks:

- Python 3.10 compilation for Forge extension sources;
- JavaScript syntax for Forge-side and Browser Bridge scripts;
- Browser Bridge `manifest.json` JSON validity.

This gate is intentionally dependency-light. It catches malformed commits without pretending to emulate a full Forge installation in CI.

## Recommended local 22.5 smoke test

### 1. Forge startup

- Update CivitaiFlow.
- Restart Forge completely.
- Confirm the CivitaiFlow tab renders.
- Confirm the visible release badge reads `v22.5`.
- Confirm the library status row appears below the Civitai connection card.

### 2. First library index

- Wait for the index status to move from `Library indexing` to an indexed asset count.
- Confirm LoRA and checkpoint counts are plausible.
- Click **Reindex** and confirm a new scan starts without freezing the Forge UI.

### 3. Existing-model recognition

Choose a Civitai model that is already present locally.

Expected Browser Bridge state:

```text
Installed
```

Clicking the installed control must not create another model file.

### 4. New-version recognition

Choose a Civitai model for which an older local version exists.

Expected state when the remote/current target differs:

```text
Update available
```

Sending it to Forge should preserve the older different file rather than overwrite it blindly.

### 5. New model transfer

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

### 6. Hash verification

After a successful transfer:

- inspect the generated JSON sidecar;
- confirm it contains Civitai model ID, version ID, model type, source filename and SHA-256;
- re-send the same model;
- confirm CivitaiFlow returns `Installed` and does not download the bytes again.

### 7. Checkpoint routing

Send a small/test checkpoint target if practical.

Confirm it resolves under:

```text
models/Stable-diffusion
```

and does not appear under `models/Lora`.

### 8. Browser Bridge direct mode

With Forge running on the default local port `7860`:

- load/reload `browser-extension/` in Edge/Chrome;
- open Civitai;
- confirm model cards show CivitaiFlow state;
- click **Send to Forge**;
- confirm the model queues without needing a manual clipboard copy.

### 9. Sniper fallback

Stop Forge or otherwise make the loopback bridge unavailable, then click **Send to Forge** on Civitai.

The Browser Bridge should fall back to clipboard capture. After Forge is available again, the original Sniper/manual workflow should remain usable.

### 10. Authentication regression

- Verify the saved API key through the Forge connection card.
- Open Companion Window and confirm normal Civitai website login still works independently.
- Confirm the Browser Bridge never asks for or displays the API key.

## Known CI limitation

GitHub CI does not currently boot a complete Stable Diffusion WebUI Forge runtime. The Forge callback lifecycle, Gradio composition, actual model directories and browser extension injection must still be smoke-tested locally before treating a release as fully verified.

A future integration harness should provide a lightweight fake Forge callback/runtime layer so the library index and local API can be unit-tested without loading Stable Diffusion itself.
