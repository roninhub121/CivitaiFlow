# CivitaiFlow Architecture

This document describes the product objective, the current implementation, the iframe/authentication constraints, and the recommended technical direction for future releases.

## 1. Product objective

CivitaiFlow exists to reduce the number of manual steps between **finding a Civitai asset** and **using it locally in Stable Diffusion WebUI Forge**.

The core product is not the iframe itself. The iframe was the original discovery surface because it kept Civitai visually inside Forge.

The actual value chain is:

```text
DISCOVER → CAPTURE → RESOLVE → AUTHENTICATE → DOWNLOAD → ORGANIZE → USE
```

A successful CivitaiFlow release should preserve that loop even if one discovery surface stops working.

### Success criteria

A model acquisition workflow should require as little manual work as possible after discovery:

- the user finds a model;
- a Civitai model URL is copied or pasted;
- CivitaiFlow resolves the model automatically;
- required authentication is applied automatically;
- the transfer runs in the background;
- the model is written safely to the correct Forge library;
- preview and metadata are created;
- failures are visible and retryable.

## 2. Current system

### Presentation layer

- Forge / Gradio tab.
- Embedded `civitai.com` iframe.
- Civitai API connection card.
- Capture controls.
- Activity/telemetry panel.
- Same-browser Companion Window enhancement in `javascript/civitai_flow.js`.

### Capture layer

The current zero-click workflow uses a PowerShell subprocess to read the Windows clipboard periodically.

Why a subprocess is used:

- clipboard access is isolated from Forge's Python process;
- it avoids direct Windows API lifetime/locking problems inside async/UI threads;
- failure of clipboard access does not crash the main process.

### Acquisition layer

The Python extension:

1. parses Civitai model IDs from captured text;
2. calls the Civitai REST API;
3. resolves model metadata and a downloadable `.safetensors` file;
4. authenticates with `Authorization: Bearer <key>` when configured;
5. downloads with background workers;
6. reports transfer progress;
7. writes through a `.part` file and renames on success.

### Forge integration layer

The current target is the Forge LoRA directory.

For each downloaded model CivitaiFlow also attempts to write:

- preview image;
- JSON metadata;
- base model;
- activation text;
- Civitai model ID;
- Civitai version ID.

## 3. Authentication is two separate systems

### Website authentication

The embedded Civitai website uses browser cookies and Civitai's normal website login flow.

CivitaiFlow cannot turn a REST API key into a browser login session without unsupported cookie/session manipulation.

### API authentication

The backend uses a Civitai bearer credential for API requests and gated downloads.

This is independent from the iframe's cookie jar.

This separation is intentional and should remain explicit in the UI and documentation.

## 4. The iframe is an external dependency, not a stable API

The original CivitaiFlow experience assumed that Civitai could be embedded indefinitely. That assumption is not safe enough for the product architecture.

There are three independent constraints.

### 4.1 OAuth user-agent restrictions

Google can reject OAuth authorization when it is presented through an embedded user-agent/webview. This is the source of the Google 403 behavior seen from the embedded flow.

The correct solution is to perform login in a normal top-level browser context.

### 4.2 Anti-framing policy

The remote website decides whether it may be embedded. `X-Frame-Options` and CSP `frame-ancestors` can reject an iframe before application code has any opportunity to compensate.

Civitai's upstream application has used anti-framing headers, so embedded mode must be treated as best-effort rather than a guaranteed contract.

### 4.3 Third-party cookie policy

Even when a site renders inside an iframe, browsers can block or partition third-party cookie state. A user may therefore be signed in to `civitai.com` as a top-level page while the same site appears logged out when embedded under a local Forge origin.

The Storage Access API can help only when the embedded site itself participates in the permission flow. The parent Forge page cannot unilaterally grant Civitai access to blocked cookies.

## 5. Discovery strategy

The product should have two first-class discovery surfaces.

### Embedded mode

Use when it works.

Advantages:

- single-tab experience;
- original CivitaiFlow interaction model;
- visually integrated with Forge.

Disadvantages:

- controlled by remote framing policy;
- login is not reliable;
- browser cookie policy can break account state.

### Companion Window mode

Open `civitai.com` as a normal top-level window from the Forge browser.

Advantages:

- normal Google/Civitai login;
- first-party website cookies;
- not affected by iframe anti-framing policy;
- still works with Sniper clipboard capture;
- works better when Forge is accessed remotely because the window is opened client-side rather than with Python's host-side `webbrowser` module.

Disadvantages:

- not visually inside the Forge tab;
- clipboard remains the bridge between discovery and acquisition.

The Companion Window is the preferred resilience mechanism because it preserves the real workflow instead of attempting to bypass browser security controls.

## 6. Why API auth cannot log the iframe in

A Civitai API key authenticates HTTP API requests made by CivitaiFlow. A website session is represented by cookies/session state issued by Civitai's web authentication system.

These credentials are not interchangeable.

CivitaiFlow should not:

- manufacture Civitai session cookies from an API token;
- scrape cookies from Chrome/Edge/Firefox profiles;
- inject a user's API key into Civitai website JavaScript;
- proxy Civitai through localhost merely to remove anti-framing headers.

Those approaches would be fragile, increase credential exposure, and couple the extension to undocumented internal behavior.

## 7. OAuth direction

Civitai now exposes official OAuth building blocks for third-party applications using Authorization Code + PKCE.

This is a promising future replacement for manually copying a personal API key.

A CivitaiFlow-native OAuth implementation should use:

```text
Forge extension
  ↓ generate state + PKCE verifier/challenge
Normal browser / auth.civitai.com
  ↓ user approves
Loopback callback on 127.0.0.1
  ↓ authorization code
Token exchange
  ↓
Access token + refresh token
```

For a local desktop-style client, a public OAuth client with PKCE is preferable to embedding a client secret in the extension.

### Prerequisite

CivitaiFlow needs its own registered Civitai OAuth client (client ID + allowed redirect URI/scopes). We should not reuse another application's client ID.

### Important

OAuth would improve **API authentication UX**. It still would not guarantee that the embedded Civitai website receives a first-party browser session inside an iframe.

## 8. Deep implementation audit

### P0 — iframe availability is outside our control

**Impact:** the most visible part of the UI can disappear or reject login without a CivitaiFlow code regression.

**Decision:** keep embedded mode, but never make core acquisition depend on it. Companion mode is the supported fallback.

### P1 — model routing currently assumes LoRA storage

The current download path writes into the Forge LoRA directory. A copied Civitai URL can represent other resource types.

**Risk:** a checkpoint/other `.safetensors` resource can be routed incorrectly.

**Recommended next change:** introduce a model router based on Civitai `type` and reject unsupported types explicitly until routing exists.

### P1 — version-aware links are not fully honored

A Civitai URL may contain `modelVersionId`. The current capture flow primarily extracts the model ID and then selects the first version returned by the API.

**Risk:** the downloaded version can differ from the version the user intentionally copied.

**Recommended next change:** parse and preserve `modelVersionId`; use it as the resolver's preferred version.

### P1 — secret storage is not encrypted by CivitaiFlow

The API key is persisted through Forge's settings/configuration system.

**Risk:** anyone who can read the Forge configuration files may be able to recover the key.

**Recommended next change:** optional Windows DPAPI/Credential Manager storage while preserving Forge config compatibility.

### P2 — global in-memory state assumes one local user

Download status, processed IDs, failed IDs, and clipboard state are module globals.

**Risk:** multiple browser clients connected to the same Forge process share state.

**Recommended next change:** document local single-user scope; introduce a queue/service abstraction before supporting multi-user Forge deployments.

### P2 — Sniper capture is Windows-specific

Clipboard capture shells out to PowerShell.

**Risk:** the extension is not portable to Linux/macOS without another capture provider.

**Recommended next change:** provider interface (`WindowsPowerShellClipboard`, optional JS/manual capture providers).

### P2 — folder organization is based on the first remote tag

The first Civitai tag is not a stable taxonomy for local model storage.

**Risk:** inconsistent directory structures over time.

**Recommended next change:** base-model/type routing with optional user-defined category rules.

### P2 — no post-download integrity verification

A completed HTTP transfer is renamed into place without comparing the downloaded file to a known Civitai hash.

**Risk:** corrupted content can look complete.

**Recommended next change:** use Civitai file hashes when present and verify SHA-256 before final rename.

### P2 — remote API/site behavior needs compatibility boundaries

CivitaiFlow calls public Civitai endpoints but still depends on response shape and website behavior.

**Recommended next change:** isolate Civitai access behind a client module rather than mixing HTTP, UI, and download logic in one large script.

## 9. Target architecture

A maintainable next major version should separate the current monolithic Python script into explicit components.

```text
scripts/
  civitai_flow.py              # Forge/Gradio composition
  civitai_client.py            # REST/auth client
  resolver.py                  # model + version resolution
  download_manager.py          # queue/workers/retries/progress
  storage_router.py            # LoRA/checkpoint/VAE/etc routing
  metadata.py                  # Forge metadata/preview handling
  clipboard.py                 # capture providers

auth/
  api_key.py                   # current bearer auth
  oauth_pkce.py                # future registered OAuth client

javascript/
  civitai_flow.js              # companion-window/browser UX
```

### Target data flow

```text
Embedded Civitai ──────┐
                       ├─→ URL capture → Resolver → Download Manager → Storage Router → Forge
Companion Window ──────┘                    ↑
                                            │
                                  API key / OAuth token
```

## 10. Recommended implementation order

1. **Protect the core loop from iframe failure** — complete Companion Window UX and documentation.
2. **Version-aware resolver** — preserve `modelVersionId`.
3. **Model-type guard/router** — never silently place unsupported assets in LoRA.
4. **Hash verification** — validate completed files before atomic rename.
5. **Split Civitai client/download manager from Gradio UI**.
6. **Register CivitaiFlow OAuth client**.
7. **Implement OAuth Authorization Code + PKCE**.
8. **Optional secure credential storage**.
9. **Expand to checkpoints, VAE, embeddings, ControlNet, etc.**

## 11. Non-goals

CivitaiFlow should not become:

- a replacement Civitai social client;
- a browser-security bypass tool;
- a reverse proxy for the entire Civitai site;
- a credential/cookie extractor;
- a second Stable Diffusion model manager unrelated to the discovery-to-download workflow.

The product should stay focused: **discover on Civitai, acquire safely, use in Forge.**
