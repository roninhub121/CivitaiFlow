# CivitaiFlow Troubleshooting

This guide is symptom-first. Start with what Forge actually shows, then follow the smallest corrective path.

## Fast diagnostic matrix

| Symptom | Most likely cause | Corrective action |
| --- | --- | --- |
| Huge CivitaiFlow logo | Runtime is using the old UI path or stale extension files | Update to 22.7.2, verify the checkout, restart Forge completely, hard-refresh once |
| Embedded Civitai is a tiny ~300×150 box | Gradio ignored nested `Blocks(css=...)` and only the toolbar JavaScript loaded | 22.7.2 moves critical shell ownership into the already-proven `javascript/civitai_flow.js` path |
| Large empty area beside tiny iframe | Parent browser shell is full-width but iframe kept browser-default dimensions | 22.7.2 sets frame and iframe dimensions both through head CSS and runtime inline guards |
| Badge still says `v22.5` | Stale JavaScript is still executing from an older checkout/browser session | Verify Git HEAD, restart Forge, hard-refresh, then query `/civitaiflow/api/release` |
| Companion/Reload look correct while everything else is broken | Strong evidence that `javascript/civitai_flow.js` loads while nested Gradio CSS does not | This exact signal is the reason 22.7.2 consolidates the premium shell into that script |
| Google/Civitai login fails inside embedded view | Browser/OAuth policy rejects embedded authentication | Use **Companion** for normal top-level browser authentication |
| **Get API Key** opens the wrong page | Legacy `/user/settings` fallback or stale Python runtime | 22.7.2 routes to `/user/account`; restart Forge after updating |
| `Library index · service unavailable` | Python feature layer failed to load or Forge was not restarted | Restart Forge and inspect the first CivitaiFlow traceback |
| `0 indexed` forever | No supported assets found, paths differ, or index worker failed | Click **Reindex**, inspect Forge model folders, then inspect console/data state |
| Browser Bridge says Forge unavailable | Forge stopped or listening outside common ports | 0.3.0 checks 7860–7863 on `127.0.0.1` and `localhost` |
| `.part` remains after interruption | Transfer stopped before verification | Resume through CivitaiFlow; never rename `.part` manually |

---

## 1. Giant logo + tiny iframe + working Companion toolbar

This combination is now treated as a specific runtime signature, not a generic styling complaint.

The broken state looks like this:

- the SVG logo expands to an intrinsic/browser size;
- the Civitai iframe stays near its default HTML size;
- the browser workspace around it is mostly empty;
- **Companion / Reload** still look styled and are positioned correctly.

That last point matters. The Companion toolbar is created by `javascript/civitai_flow.js`. If it renders correctly while the rest is broken, the browser script is alive and the nested Gradio CSS path is the unreliable part.

### 22.7.2 architecture

22.7.2 consolidates the Forge shell into the execution path already proven by the broken runtime:

```text
javascript/civitai_flow.js
        ↓
head-level runtime stylesheet
        ↓
DOM layout marking
        ↓
critical inline dimensions
        ↓
release badge healing
        ↓
Companion / Reload
        ↓
Library & lifecycle host
```

The separate `javascript/premium_shell.js` experiment was removed. Two self-healing DOM loops were unnecessary and could fight over layout/version state.

The Python release layer remains only as a second fallback for critical generated HTML and release diagnostics.

---

## 2. Prove which checkout Forge is actually executing

Before debugging CSS, verify the extension checkout.

From the CivitaiFlow extension directory:

```powershell
git status --short --branch
git remote -v
git rev-parse --show-toplevel
git rev-parse --short HEAD
git log -1 --oneline
```

Then search Forge for duplicate copies:

```powershell
Get-ChildItem C:\stable-diffusion-webui-forge -Directory -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match 'CivitaiFlow|civitai-flow' } |
    Select-Object FullName
```

If two extension copies exist, Forge may be executing one while you are updating another.

Do not delete anything blindly. First identify which copy is actually under the active Forge `extensions` path.

---

## 3. Required recovery sequence after a code update

```text
1. Pull the current main branch.
2. Verify HEAD changed.
3. Stop Forge completely.
4. Start Forge again.
5. Reload Browser Bridge if installed.
6. Hard-refresh the Forge browser once.
7. Open CivitaiFlow.
8. Verify v22.7.2.
9. Query /civitaiflow/api/release.
```

A browser refresh alone cannot reload Python extension modules.

---

## 4. Release health endpoint

22.7.2 exposes:

```text
GET /civitaiflow/api/release
```

Expected:

```json
{
  "ok": true,
  "version": "22.7.2",
  "interface": "runtime-shell-v2",
  "runtimeScript": "javascript/civitai_flow.js",
  "browserBridge": "0.3.0"
}
```

Interpretation:

- endpoint missing → final Python release layer did not load;
- endpoint says older version → stale Python checkout/runtime;
- endpoint says 22.7.2 but UI badge is older → stale browser JavaScript/cache;
- badge says 22.7.2 but endpoint is missing → browser shell updated, Python layer did not.

This distinction avoids guessing.

---

## 5. Embedded login does not work

CivitaiFlow separates:

- **website session** — Civitai cookies/login;
- **API key** — Forge-side authenticated API/download access.

They are not interchangeable.

Embedded authentication can fail because third-party cookies, framing policy, or an OAuth provider rejects embedded user-agents. Use **Companion** for authentication; it opens a normal top-level Civitai window in the same browser profile.

---

## 6. API key does not connect

Use:

```text
Get API Key ↗
→ Civitai account page
→ create/copy personal API key
→ paste into CivitaiFlow
→ Connect API
→ Verify
```

Expected success:

```text
Connected as <username>
API authentication active
```

Never post the key in screenshots, logs, GitHub issues, commits, or documentation.

---

## 7. Library is empty or stuck

Primary indexed locations:

| Type | Forge path |
| --- | --- |
| LoRA | `models/Lora` |
| Checkpoint | `models/Stable-diffusion` |
| VAE | `models/VAE` |
| Textual Inversion | `<data-dir>/embeddings` |

Supported extensions include `.safetensors`, `.ckpt`, `.pt`, and `.bin`.

If the index remains zero:

1. confirm model files exist in those paths;
2. click **Reindex**;
3. wait for indexing to finish;
4. inspect the Forge console if status becomes unavailable/error;
5. inspect `<data-dir>/civitai-flow/library-index.json` only for deeper diagnosis.

Do not delete the index as the first step.

---

## 8. Browser Bridge cannot find Forge

Browser Bridge 0.3.0 probes:

```text
127.0.0.1:7860–7863
localhost:7860–7863
```

It remembers the working base after discovery. The bridge remains loopback-oriented and is not intended to expose control endpoints over a LAN/public interface.

---

## 9. Interrupted downloads

Expected lifecycle:

```text
Downloading
→ Forge closes / connection drops
→ Interrupted
→ Resume
→ SHA-256 verification
→ Installed
```

If HTTP Range is supported, CivitaiFlow resumes. If not, it safely restarts that transfer instead of appending incompatible bytes.

Never manually rename `.part` to a model extension.

---

## 10. What to attach to a bug report

Useful evidence:

- full CivitaiFlow screenshot;
- `/civitaiflow/api/release` response;
- `git rev-parse --short HEAD` from the active extension directory;
- Forge build/commit;
- browser name/version;
- Forge launch port;
- first relevant Forge console traceback;
- whether Companion works;
- whether the problem reproduces after a full restart.

Remove API keys, cookies, Authorization headers and other secrets first.
