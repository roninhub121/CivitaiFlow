# CivitaiFlow Authentication

CivitaiFlow interacts with Civitai through two fundamentally different authentication contexts:

1. the **Civitai website session** rendered by a browser;
2. the **Civitai API credential** used by the Forge extension backend.

They solve different problems and should not be treated as interchangeable.

## Authentication matrix

| Mechanism | Where it runs | What it authenticates | Can sign the website iframe in? | Current status |
| --- | --- | --- | --- | --- |
| Civitai website login | Top-level browser / Companion Window | Civitai web UI, account pages, first-party cookies | Maybe, only if browser cookie/framing policy permits reuse | Supported |
| Personal Civitai API key | Forge Python backend | REST metadata and gated downloads | No | Supported |
| Civitai OAuth + PKCE | Top-level browser + local callback | Future API access tokens | No guarantee | Planned |
| Embedded Google OAuth | Civitai iframe | Google authorization flow | N/A | Not reliable / should not be used |

## 1. Website authentication

The Civitai website uses its own browser session.

When Civitai is opened as a top-level page, the browser can store first-party Civitai cookies normally. This is why **Open Companion Window** is the preferred login surface.

### Recommended flow

1. Open **Companion Window** from Forge.
2. Sign in to Civitai there.
3. Browse normally.
4. Copy model URLs as usual; Sniper capture remains active in Forge.
5. Close the companion window when finished.
6. CivitaiFlow attempts to reload the iframe.

The iframe may or may not inherit the authenticated state after reload.

### Why the iframe can still be logged out

Forge usually runs on a local origin such as `http://127.0.0.1:7860`, while the embedded page comes from `https://civitai.com`.

That makes Civitai a third-party context relative to the Forge page.

Modern browsers may:

- block third-party cookies;
- partition them by top-level site;
- require explicit storage-access permission;
- apply site-specific anti-tracking rules.

Opening Civitai successfully in a top-level popup/window proves that the account login works. It does not force the browser to expose that first-party cookie jar to a cross-site iframe.

## 2. Google OAuth inside an iframe

Google's OAuth policies reject authorization in unsupported embedded user-agents/webviews. In practice, an iframe-originated Google sign-in can end in HTTP 403 / `disallowed_useragent`.

CivitaiFlow should not attempt to bypass this.

The supported UX is to move only the login step to a normal browser window while keeping CivitaiFlow's acquisition workflow active in Forge.

## 3. Anti-framing headers

Even if authentication succeeds, the remote site can refuse to render in an iframe.

The relevant controls include:

```http
X-Frame-Options: DENY
```

and CSP policies such as:

```http
Content-Security-Policy: frame-ancestors ...
```

These are enforced by the browser before CivitaiFlow can meaningfully interact with the page.

The current upstream Civitai application has used `X-Frame-Options: DENY` broadly, which is why the embedded view is classified as **best-effort** rather than a durable integration contract.

## 4. Storage Access API

The browser platform has a Storage Access API for legitimate third-party embeds that need access to unpartitioned cookies.

However, it requires cooperation from the **embedded document**.

In other words:

- Forge can allow a storage-access capability;
- Civitai itself would need to detect/request storage access from inside its iframe;
- the browser may prompt the user;
- the parent extension cannot simply grant itself access to Civitai's cookies.

Therefore this is not a workaround CivitaiFlow can implement unilaterally.

## 5. API authentication

CivitaiFlow currently supports a personal Civitai API key.

The extension sends it using a Bearer header:

```http
Authorization: Bearer <CIVITAI_API_KEY>
```

The current connection test calls:

```http
GET https://civitai.com/api/v1/me
```

If the request succeeds, the key is persisted through Forge's configuration system.

### What the API key enables

Depending on the token scope/account state, it can enable:

- authenticated user identity;
- model metadata unavailable to anonymous requests;
- gated/restricted model downloads;
- access to content allowed by the account's Civitai settings;
- higher authenticated API limits where Civitai provides them.

### What it does not do

An API key does not:

- create a Civitai browser cookie;
- complete Google sign-in;
- automatically authenticate the iframe;
- bypass content restrictions outside the token/account's permissions.

## 6. Creating the current API key

Use Civitai's Account page:

`https://civitai.com/user/account`

Then:

1. sign in;
2. find **API Keys**;
3. create a new key;
4. copy it;
5. paste it into CivitaiFlow;
6. click **Connect API**.

### Scope guidance

Civitai now supports scoped token capabilities. For the current CivitaiFlow use case, prefer the least privileged key that can:

- read the current user identity (`UserRead` equivalent);
- browse/read models (`ModelsRead` equivalent);
- download the desired resources.

Do not grant write/generation/social scopes unless a future CivitaiFlow feature actually needs them.

## 7. Secret storage

CivitaiFlow currently saves the API key through Forge's normal settings mechanism.

The UI masks the token, but masking is not encryption.

Security assumptions:

- Forge is primarily a local single-user application;
- the machine account and Forge configuration directory are trusted;
- the Forge web UI should not be exposed to untrusted networks without additional access controls.

Future hardening can add Windows DPAPI or Credential Manager while keeping the existing Forge setting as a compatibility fallback.

## 8. Companion Window implementation

`javascript/civitai_flow.js` upgrades the existing browser actions to open Civitai from the browser running Forge rather than relying only on Python's `webbrowser.open()`.

This matters because:

- a client-side popup uses the user's actual browser profile;
- the user sees normal first-party Civitai behavior;
- Google OAuth runs in a supported top-level context;
- remote Forge sessions open Civitai on the client instead of the Forge host;
- Sniper clipboard capture continues to bridge the browsing surface and Forge.

The script also attempts to reload the embedded panel when the companion window is closed.

That reload is best-effort; it cannot override framing or third-party-cookie policy.

## 9. Future: official OAuth Authorization Code + PKCE

Civitai now publishes OAuth tooling for third-party applications, including Authorization Code + PKCE and support for public clients.

This creates a path to replace manual API-key copy/paste with a real **Connect with Civitai** flow.

### Desired desktop/local flow

```text
1. CivitaiFlow generates:
   - state
   - PKCE verifier
   - PKCE S256 challenge

2. CivitaiFlow starts a temporary loopback callback:
   http://127.0.0.1:<port>/callback

3. The browser opens Civitai authorization.

4. The user approves the requested scopes.

5. Civitai redirects the authorization code to the loopback callback.

6. CivitaiFlow exchanges:
   code + verifier → access token (+ refresh token)

7. The extension stores/refreshes the token securely.
```

### Why PKCE

A Forge extension is distributed to end-user machines. A static client secret embedded in the repository would not be secret.

A **public OAuth client + PKCE** is therefore the correct client model if Civitai registration permits the required loopback redirect/scopes.

### Prerequisite

CivitaiFlow must have its **own** OAuth client registration.

Do not reuse:

- Civitai CLI client IDs;
- another third-party application's client ID;
- copied client secrets from unrelated projects.

### OAuth still does not equal website iframe login

Even after OAuth is implemented, the resulting access token is an API credential. It should not be converted into Civitai website cookies by the extension.

OAuth improves API connection UX and token lifecycle; it does not remove browser anti-framing or third-party-cookie constraints.

## 10. Device authorization as a possible future UX

Civitai's own CLI demonstrates that device authorization can be useful for local tools: the local client displays a verification URL/code and the user approves in a browser.

A device flow could be attractive for CivitaiFlow if Civitai provides/approves an OAuth client registration for this extension with the necessary model-read/download scopes.

It should be evaluated after client registration, not implemented by borrowing Civitai CLI credentials.

## 11. Approaches intentionally rejected

### Scraping browser cookies

Rejected because it requires browser-specific profile decryption/access, dramatically expands credential exposure, and couples the extension to private browser storage formats.

### Setting website cookies from an API key

Rejected because API credentials and website sessions are different security domains. There is no supported transformation from a personal API token into a Civitai web session cookie.

### Reverse proxy that strips anti-framing headers

Rejected because it deliberately defeats the remote site's clickjacking/framing controls and creates a large compatibility/security burden around cookies, redirects, scripts, CSP, CSRF, assets, and OAuth.

### Browser extension that removes `X-Frame-Options`

Not a supported CivitaiFlow dependency. It would ask users to weaken browser security to preserve a convenience surface.

## 12. Decision summary

The supported authentication architecture is:

```text
Civitai website account
      │
      ├─ top-level Companion Window ──→ website session / normal login
      │
      └─ personal API key ────────────→ CivitaiFlow API + downloads

Forge iframe ──→ convenience only; may or may not see the website session
```

Future target:

```text
Personal API key (current)
          ↓
Official Civitai OAuth + PKCE (future default)
```

The core acquisition engine must remain useful regardless of iframe state.
