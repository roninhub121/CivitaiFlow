# CivitaiFlow 22.7.2 — Runtime Shell Consolidation

**Release class:** emergency stabilization / UI architecture correction  
**Target:** Stable Diffusion WebUI Forge  
**Primary regression:** giant product mark + browser-default Civitai iframe + stale release identity

## Executive summary

22.7.2 is the corrective follow-up to 22.7.1 after real Forge evidence showed that the previous compatibility strategy was still too indirect.

The important observation was not merely that the interface looked broken. The screenshot showed a very specific split state:

- CivitaiFlow branding and base cards were effectively unstyled;
- the embedded Civitai iframe stayed close to browser-default dimensions;
- the surrounding browser workspace itself existed;
- the **Companion / Reload** toolbar remained styled and correctly positioned.

That proved `javascript/civitai_flow.js` was executing while the nested Gradio CSS path was not dependable in the installed Forge composition.

22.7.2 therefore moves the premium runtime shell into the JavaScript file that the broken runtime already proved it could execute.

---

## Root cause

The original UI depended on styling passed through:

```text
gr.Blocks(css=custom_css)
```

That path is not reliable across every Forge/Gradio composition.

When it is ignored, HTML falls back to intrinsic browser behavior:

```text
SVG → oversized intrinsic rendering
iframe → approximately 300 × 150
cards → Forge defaults
browser column → still occupies space
```

At the same time, `javascript/civitai_flow.js` continued to inject the Companion toolbar into `<head>`, which is why that small part of the interface still looked correct.

That surviving code path became the new source of truth.

---

## Architecture change

### Before

```text
ronin_ui.py
   ↓
nested Blocks CSS
   ↓
premium_shell.js compatibility layer
   ↓
release.py fallback
```

The browser could end up with multiple styling owners and multiple self-healing loops.

### 22.7.2

```text
ronin_ui.py
   ↓
javascript/civitai_flow.js  ← canonical browser runtime shell
   ├─ head stylesheet
   ├─ DOM layout markers
   ├─ inline critical dimensions
   ├─ version healing
   ├─ Library & lifecycle host
   └─ Companion / Reload

zzzzz_civitaiflow_release.py
   └─ Python-side critical fallback + release diagnostic
```

The separate `javascript/premium_shell.js` file was removed.

---

## Runtime guarantees

The canonical browser shell now explicitly enforces:

- product mark container: 36 × 36 px;
- product SVG: 30 × 30 px;
- desktop control rail: approximately 340–400 px;
- browser workspace: fluid remaining width;
- iframe width: 100%;
- iframe height: workstation-sized, minimum 640 px on desktop;
- no inherited prose/max-width constraint on the browser workspace;
- responsive medium and narrow layouts;
- dedicated **Library & lifecycle** host;
- visible release identity: `v22.7.2`.

Critical logo and iframe dimensions are applied twice:

1. through the head-level runtime stylesheet;
2. directly through `element.style.setProperty(..., "important")` at runtime.

The Python release layer also keeps inline HTML dimensions as a second-language fallback.

---

## Release diagnostics

Local endpoint:

```text
GET /civitaiflow/api/release
```

Expected response:

```json
{
  "ok": true,
  "version": "22.7.2",
  "interface": "runtime-shell-v2",
  "runtimeScript": "javascript/civitai_flow.js",
  "browserBridge": "0.3.0"
}
```

This endpoint is now part of the support contract because it separates four common failure modes:

| Diagnostic | Interpretation |
| --- | --- |
| endpoint missing | Python release layer did not load |
| endpoint reports old version | stale checkout or stale Forge process |
| endpoint 22.7.2, UI old | stale browser JavaScript/cache |
| UI 22.7.2, endpoint missing | browser layer updated, Python layer stale |

---

## Upgrade procedure

From the active CivitaiFlow extension checkout:

```powershell
git pull origin main
git status --short --branch
git rev-parse --short HEAD
git log -1 --oneline
```

Then:

```text
1. Stop Forge completely.
2. Start Forge again.
3. Reload Browser Bridge if installed.
4. Hard-refresh the Forge browser once.
5. Open CivitaiFlow.
6. Confirm v22.7.2.
7. Open /civitaiflow/api/release.
```

A browser refresh alone is not a valid verification after Python files changed.

---

## Acceptance criteria

22.7.2 is locally acceptable only when all are true:

- logo is compact;
- release badge is `v22.7.2`;
- embedded Civitai fills the browser workspace;
- there is no large blank region caused by a default-size iframe;
- control rail remains readable and bounded;
- Library & lifecycle is separated from API credential controls;
- Companion works as a top-level Civitai window;
- release diagnostic returns the expected contract;
- GitHub `validate` is green.

---

## Engineering principle established

For Forge extensions, a styling mechanism is not considered reliable merely because it is valid Gradio API usage.

A critical UI surface must be attached to an execution path proven in the target runtime. In this case the surviving Companion toolbar demonstrated that extension JavaScript injection was more reliable than nested `Blocks(css=...)`, so the product shell was moved there instead of adding another compatibility layer on top.

See also:

- [Testing](TESTING.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Architecture](ARCHITECTURE.md)
