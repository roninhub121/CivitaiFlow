# CivitaiFlow Troubleshooting

This guide is intentionally symptom-first. Start with what Forge actually shows, then follow the smallest corrective path.

## Fast diagnostic matrix

| Symptom | Most likely cause | Corrective action |
| --- | --- | --- |
| Huge CivitaiFlow logo | Forge/Gradio ignored nested extension CSS | Update to 22.7.1, restart Forge completely, hard-refresh once |
| Embedded Civitai is a tiny ~300×150 box | Same CSS injection failure / HTML wrapper constrained the iframe | 22.7.1 premium shell applies head-level CSS plus critical inline dimensions |
| Large empty area beside a tiny iframe | Browser column inherited Gradio max-width/layout constraints | 22.7.1 marks the runtime shell and removes wrapper max-width constraints |
| Version badge falls back to `v22.5` | Legacy Library Intelligence JavaScript was overwriting the product badge | 22.7.1 removes the stale badge writer and owns release identity in the final release layer |
| Google/Civitai login fails inside embedded view | Browser/OAuth policy rejects embedded authentication | Use **Companion** for normal top-level browser authentication |
| **Get API Key** opens the wrong Civitai page | Legacy `/user/settings` fallback | 22.7.1 final release layer routes to `/user/account` |
| API Verify returns rejected/401/403 | Missing, invalid, expired or gated API token | Create/copy a current personal key from Civitai account settings and reconnect |
| `Library index · service unavailable` | Forge was not fully restarted after updating or one compatibility layer failed to load | Restart Forge; inspect console for CivitaiFlow traceback; re-run Git update if needed |
| `0 indexed` forever | No supported assets found, model paths differ, or index worker failed | Click **Reindex**, inspect Forge model folders, then inspect console/data state |
| Browser Bridge says Forge unavailable | Forge is stopped or listening outside common local ports | 0.3.0 checks 7860–7863 on both `127.0.0.1` and `localhost`; use Sniper fallback outside that range |
| Download leaves `.part` after interruption | Transfer was interrupted before verification | Restart Forge and use/resume the persisted queue; do not rename `.part` manually |
| Model downloads twice | Local metadata/hash index was missing or stale | Reindex; CivitaiFlow compares SHA-256 and version identity before transfer |

---

## 1. Giant logo or tiny embedded browser

### What this means

The screenshot pattern is very specific:

- SVG renders at a browser/default intrinsic size instead of the intended compact mark;
- iframe renders close to its browser default size;
- the toolbar injected by JavaScript can still look styled;
- the rest of the Gradio card styling is absent.

That combination means the extension itself loaded, but the CSS passed through nested `gr.Blocks(css=...)` was not reliably applied by that Forge/Gradio composition.

### 22.7.1 fix

22.7.1 no longer depends on that single styling path.

It uses three layers:

1. **head-level premium stylesheet** from `javascript/premium_shell.js`;
2. **runtime DOM hooks** that identify the actual sidebar/browser wrappers produced by the installed Gradio build;
3. **critical inline dimensions** from the final Python release layer for the logo and iframe.

So a future theme/Gradio change has to break several independent safeguards before the UI falls back to the giant-logo/tiny-iframe state again.

### Recovery

```text
1. Update CivitaiFlow
2. Stop Forge completely
3. Start Forge again
4. Hard-refresh the browser once
5. Open CivitaiFlow
```

A tab refresh without restarting Forge is insufficient after Python compatibility-layer changes.

---

## 2. Embedded login does not work

CivitaiFlow intentionally separates two concepts:

- **website session** — cookies/login used by the real Civitai page;
- **Civitai API key** — token used by Forge-side metadata/download requests.

They are not interchangeable.

Embedded authentication can fail because third-party cookies, framing policy, or an OAuth provider rejects embedded user-agents. That does not mean the CivitaiFlow API integration is broken.

Use **Companion** for authentication. It opens Civitai as a normal top-level browser window in the same browser profile.

---

## 3. API key does not connect

Use this sequence:

```text
Get API Key ↗
→ Civitai account page
→ create/copy personal API key
→ paste into CivitaiFlow
→ Connect API
→ Verify
```

Expected success state:

```text
Connected as <username>
API authentication active
```

The key is stored in Forge settings. The Browser Bridge never needs to receive the raw key.

Do not paste API keys into GitHub issues, screenshots, logs, commits, or documentation.

---

## 4. Library is empty or stuck

CivitaiFlow indexes supported local assets before smart acquisition so it can prevent duplicates.

Primary locations:

| Type | Forge path |
| --- | --- |
| LoRA | `models/Lora` |
| Checkpoint | `models/Stable-diffusion` |
| VAE | `models/VAE` |
| Textual Inversion | `<data-dir>/embeddings` |

Supported model file extensions currently include `.safetensors`, `.ckpt`, `.pt`, and `.bin`.

If the index remains at zero:

1. confirm files exist in those paths;
2. click **Reindex**;
3. wait for the status to leave `Library indexing`;
4. inspect the Forge console if the status becomes `service unavailable` or reports an error;
5. inspect `<data-dir>/civitai-flow/library-index.json` only if deeper diagnosis is required.

Do not delete the library index as a first troubleshooting step; **Reindex** is the safe path.

---

## 5. Browser Bridge cannot find Forge

Browser Bridge 0.3.0 probes these loopback endpoints:

```text
127.0.0.1:7860–7863
localhost:7860–7863
```

Once one responds, it becomes the preferred base for later requests.

The bridge is deliberately loopback-oriented. It is not designed to expose CivitaiFlow control endpoints over a LAN or public interface.

If Forge runs on a different port, the normal Sniper/clipboard workflow remains the fallback until that port is explicitly supported/configured.

---

## 6. Interrupted downloads

CivitaiFlow persists transfer state and keeps `.part` files for resumable transfers.

Expected lifecycle:

```text
Downloading
→ Forge closes / connection drops
→ Interrupted
→ Resume
→ Verifying SHA-256
→ Installed
```

If the remote server honors HTTP Range, CivitaiFlow resumes from the existing byte count. If it ignores Range and returns a full file, CivitaiFlow restarts that transfer from zero instead of appending incompatible bytes.

Never manually rename a `.part` file to a model extension. Verification is the boundary that promotes a transfer into the library.

---

## 7. Update Center says service unavailable

After updating from a release before 22.6/22.7, Forge may still be running with the old Python module set in memory.

Required action:

```text
Full Forge restart
```

If the problem remains, confirm all compatibility layers exist:

```text
scripts/ronin_ui.py
scripts/zz_civitaiflow_library.py
scripts/zzz_civitaiflow_updates.py
scripts/zzzz_civitaiflow_lifecycle.py
scripts/zzzzz_civitaiflow_release.py
```

Then check the Forge startup console for the first CivitaiFlow traceback rather than debugging secondary UI symptoms.

---

## 8. What to attach to a bug report

Useful evidence:

- CivitaiFlow release shown in the tab;
- Forge build/commit;
- browser name/version;
- Forge launch port;
- screenshot of the full CivitaiFlow tab;
- relevant Forge console traceback;
- whether Companion works;
- whether `/civitaiflow/api/release` responds locally;
- whether the issue reproduces after a full Forge restart.

Remove API keys, cookies, Authorization headers and other secrets before sharing logs.

## Release health endpoint

22.7.1 exposes a small loopback release contract:

```text
GET /civitaiflow/api/release
```

Expected shape:

```json
{
  "ok": true,
  "version": "22.7.1",
  "interface": "premium-shell-v1",
  "browserBridge": "0.3.0"
}
```

This endpoint is meant for local diagnostics and release tooling, not as a public network API.
