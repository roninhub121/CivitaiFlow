(function () {
    "use strict";

    const RELEASE_VERSION = "22.8.0";
    const CIVITAI_HOME = "https://civitai.com";
    const CIVITAI_ACCOUNT = "https://civitai.com/user/account";
    const AUTH_STATUS_URL = "/civitaiflow/api/auth-status";
    const COMPANION_NAME = "civitaiflow-companion";
    const STYLE_ID = "cf-runtime-shell-style";
    const SYSTEM_CARD_ID = "cf_system_card";
    const SYSTEM_HOST_ID = "cf_system_host";

    let companionWindow = null;
    let closeWatcher = null;
    let bindQueued = false;
    let authSyncInFlight = false;
    let lastAuthSyncAt = 0;

    function root() {
        return typeof gradioApp === "function" ? gradioApp() : document;
    }

    function appRoot() {
        return root().querySelector("#cf_root");
    }

    function findButtonByText(label) {
        const buttons = root().querySelectorAll("button");
        for (const button of buttons) {
            if ((button.textContent || "").trim() === label) return button;
        }
        return null;
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function reloadEmbeddedPanel() {
        const reload = findButtonByText("Reload Panel");
        if (reload) reload.click();
    }

    function startCloseWatcher(popup) {
        if (closeWatcher) window.clearInterval(closeWatcher);
        closeWatcher = window.setInterval(function () {
            if (!popup || popup.closed) {
                window.clearInterval(closeWatcher);
                closeWatcher = null;
                companionWindow = null;
                window.setTimeout(reloadEmbeddedPanel, 300);
            }
        }, 900);
    }

    function openCompanion(url) {
        const width = Math.min(1440, Math.max(980, Math.floor(window.screen.availWidth * 0.82)));
        const height = Math.min(1000, Math.max(720, Math.floor(window.screen.availHeight * 0.88)));
        const left = Math.max(0, Math.floor((window.screen.availWidth - width) / 2));
        const top = Math.max(0, Math.floor((window.screen.availHeight - height) / 2));
        const features = [
            "popup=yes",
            "resizable=yes",
            "scrollbars=yes",
            `width=${width}`,
            `height=${height}`,
            `left=${left}`,
            `top=${top}`,
        ].join(",");

        try {
            if (companionWindow && !companionWindow.closed) {
                companionWindow.location.href = url;
                companionWindow.focus();
                return companionWindow;
            }

            const popup = window.open("about:blank", COMPANION_NAME, features);
            if (!popup) return null;
            try { popup.opener = null; } catch (_) {}
            popup.location.href = url;
            popup.focus();
            companionWindow = popup;
            startCloseWatcher(popup);
            return popup;
        } catch (_) {
            return null;
        }
    }

    function intercept(button, url, replacementLabel, title) {
        if (!button || button.dataset.cfCompanionBound === "1") return;
        button.dataset.cfCompanionBound = "1";
        if (replacementLabel) button.textContent = replacementLabel;
        if (title) button.title = title;

        button.addEventListener(
            "click",
            function (event) {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                const popup = openCompanion(url);
                if (!popup) window.open(url, "_blank", "noopener,noreferrer");
            },
            true
        );
    }

    function iconExternal() {
        return '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M11.5 3.5h5v5M9 11l7.2-7.2M16 11.5v3A1.5 1.5 0 0 1 14.5 16h-9A1.5 1.5 0 0 1 4 14.5v-9A1.5 1.5 0 0 1 5.5 4h3"/></svg>';
    }

    function iconReload() {
        return '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M15.7 7A6.2 6.2 0 1 0 16 12M15.7 7V3.8M15.7 7h-3.2"/></svg>';
    }

    function directChildContaining(parent, node) {
        if (!parent || !node) return null;
        let current = node;
        while (current && current.parentElement && current.parentElement !== parent) {
            current = current.parentElement;
        }
        return current && current.parentElement === parent ? current : null;
    }

    function ensureRuntimeStyles() {
        if (document.getElementById(STYLE_ID)) return;

        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            #cf_root {
                --cf-border: rgba(148,163,184,.18);
                --cf-border-strong: rgba(148,163,184,.30);
                --cf-panel: rgba(15,23,42,.56);
                --cf-panel-soft: rgba(2,6,23,.30);
                --cf-text: #e5e7eb;
                --cf-muted: #94a3b8;
                --cf-accent: #f97316;
                --cf-ok: #34d399;
                --cf-warn: #fbbf24;
                --cf-error: #fb7185;
                width:100% !important;
                max-width:none !important;
                min-width:0 !important;
                padding:10px 12px 18px !important;
                box-sizing:border-box !important;
            }
            #cf_root, #cf_root * { box-sizing:border-box !important; }
            #cf_root > div, #cf_root .contain, #cf_root .wrap, #cf_root .form,
            #cf_browser_column, #cf_browser_column > div, #cf_browser_column .html-container,
            #cf_browser_column .prose { max-width:none !important; min-width:0 !important; }

            #cf_shell_row {
                display:grid !important;
                grid-template-columns:minmax(340px,400px) minmax(0,1fr) !important;
                align-items:start !important;
                gap:16px !important;
                width:100% !important;
                max-width:none !important;
                min-width:0 !important;
            }
            #cf_sidebar { width:100% !important; max-width:400px !important; min-width:0 !important; }
            #cf_browser_column { width:100% !important; max-width:none !important; min-width:0 !important; overflow:visible !important; }

            .cf-brand {
                display:flex !important;
                align-items:center !important;
                gap:12px !important;
                min-height:48px !important;
                padding:4px 4px 10px !important;
                overflow:hidden !important;
            }
            .cf-brand-mark {
                width:36px !important;
                height:36px !important;
                min-width:36px !important;
                max-width:36px !important;
                flex:0 0 36px !important;
                display:grid !important;
                place-items:center !important;
                color:var(--cf-accent) !important;
                overflow:hidden !important;
            }
            .cf-brand-mark svg {
                display:block !important;
                width:30px !important;
                height:30px !important;
                min-width:30px !important;
                min-height:30px !important;
                max-width:30px !important;
                max-height:30px !important;
            }
            .cf-brand-row { display:flex !important; align-items:center !important; gap:9px !important; line-height:1 !important; }
            .cf-brand-name { color:var(--cf-text) !important; font:760 20px/1 ui-sans-serif,system-ui,sans-serif !important; letter-spacing:-.025em !important; }
            .cf-version { display:inline-flex !important; align-items:center !important; min-height:22px !important; padding:0 7px !important; border:1px solid var(--cf-border-strong) !important; border-radius:999px !important; color:var(--cf-muted) !important; font:720 10px/1 ui-sans-serif,system-ui,sans-serif !important; }
            .cf-brand-sub { margin-top:6px !important; color:var(--cf-muted) !important; font:520 11px/1.35 ui-sans-serif,system-ui,sans-serif !important; }

            #cf_connection_card, #cf_capture_card, #cf_activity_card, #${SYSTEM_CARD_ID} {
                width:100% !important;
                min-width:0 !important;
                margin:0 0 11px !important;
                padding:13px !important;
                border:1px solid var(--cf-border) !important;
                border-radius:14px !important;
                background:linear-gradient(180deg,rgba(15,23,42,.66),rgba(15,23,42,.45)) !important;
                box-shadow:0 12px 30px rgba(0,0,0,.08) !important;
                overflow:hidden !important;
            }
            .cf-section-label { margin:0 0 10px !important; color:var(--cf-muted) !important; font:760 10px/1 ui-sans-serif,system-ui,sans-serif !important; letter-spacing:.12em !important; text-transform:uppercase !important; }
            .cf-system-copy { margin:-4px 0 8px !important; color:var(--cf-muted) !important; font:500 11px/1.4 ui-sans-serif,system-ui,sans-serif !important; }
            #${SYSTEM_HOST_ID} { width:100% !important; min-width:0 !important; }

            .cf-status { display:flex !important; align-items:center !important; gap:9px !important; min-height:44px !important; margin:0 0 10px !important; padding:9px 11px !important; border:1px solid var(--cf-border) !important; border-radius:10px !important; background:var(--cf-panel-soft) !important; }
            .cf-status-dot { width:8px !important; height:8px !important; border-radius:999px !important; flex:0 0 auto !important; background:var(--cf-muted) !important; }
            .cf-status-ok .cf-status-dot { background:var(--cf-ok) !important; }
            .cf-status-warn .cf-status-dot { background:var(--cf-warn) !important; }
            .cf-status-error .cf-status-dot { background:var(--cf-error) !important; }
            .cf-status-copy { display:flex !important; flex-direction:column !important; min-width:0 !important; line-height:1.25 !important; }
            .cf-status-copy strong { font-size:12px !important; }
            .cf-status-detail { margin-top:3px !important; color:var(--cf-muted) !important; font-size:11px !important; }

            #cf_root button { min-height:38px !important; border-radius:9px !important; font-weight:650 !important; box-shadow:none !important; }
            #cf_terminal textarea { min-height:180px !important; border:1px solid var(--cf-border) !important; border-radius:10px !important; background:rgba(2,6,23,.72) !important; color:#cbd5e1 !important; font:500 11px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace !important; }
            #cf_dropzone textarea { border:1px dashed var(--cf-border-strong) !important; border-radius:10px !important; background:rgba(2,6,23,.28) !important; }

            .cf-frame-shell {
                position:relative !important;
                display:block !important;
                width:100% !important;
                max-width:none !important;
                min-width:0 !important;
                height:clamp(640px,calc(100vh - 170px),980px) !important;
                min-height:640px !important;
                overflow:hidden !important;
                border:1px solid var(--cf-border) !important;
                border-radius:15px !important;
                background:#0b0f19 !important;
                box-shadow:0 16px 42px rgba(0,0,0,.18) !important;
            }
            .cf-frame-shell iframe {
                display:block !important;
                width:100% !important;
                max-width:none !important;
                height:100% !important;
                min-height:640px !important;
                border:0 !important;
                background:#0b0f19 !important;
            }
            .cf-browser-toolbar {
                position:absolute !important;
                top:10px !important;
                right:10px !important;
                z-index:50 !important;
                display:flex !important;
                align-items:center !important;
                gap:7px !important;
                padding:6px !important;
                border:1px solid rgba(148,163,184,.22) !important;
                border-radius:10px !important;
                background:rgba(8,12,20,.88) !important;
                box-shadow:0 8px 24px rgba(0,0,0,.24) !important;
                backdrop-filter:blur(12px) !important;
            }
            .cf-browser-chip { padding:0 6px !important; color:#94a3b8 !important; font:650 10px/30px ui-sans-serif,system-ui,sans-serif !important; letter-spacing:.06em !important; text-transform:uppercase !important; white-space:nowrap !important; }
            .cf-browser-action { appearance:none !important; display:inline-flex !important; align-items:center !important; justify-content:center !important; gap:6px !important; height:30px !important; min-height:30px !important; padding:0 9px !important; border:1px solid rgba(148,163,184,.22) !important; border-radius:8px !important; background:rgba(30,41,59,.72) !important; color:#e2e8f0 !important; font:650 11px/1 ui-sans-serif,system-ui,sans-serif !important; cursor:pointer !important; }
            .cf-browser-action:hover { background:rgba(51,65,85,.92) !important; border-color:rgba(148,163,184,.34) !important; }
            .cf-browser-action svg { width:14px !important; height:14px !important; fill:none !important; stroke:currentColor !important; stroke-width:1.7 !important; stroke-linecap:round !important; stroke-linejoin:round !important; }
            .cf-browser-action-primary { border-color:rgba(249,115,22,.42) !important; background:rgba(249,115,22,.14) !important; }
            .cf-browser-action-primary:hover { background:rgba(249,115,22,.22) !important; border-color:rgba(249,115,22,.58) !important; }

            @media (max-width:1180px) {
                #cf_shell_row { grid-template-columns:1fr !important; }
                #cf_sidebar { max-width:none !important; display:grid !important; grid-template-columns:repeat(2,minmax(0,1fr)) !important; gap:11px !important; }
                #cf_sidebar > :first-child, #cf_activity_card { grid-column:1 / -1 !important; }
                .cf-frame-shell { height:76vh !important; min-height:620px !important; }
                .cf-frame-shell iframe { min-height:620px !important; }
            }
            @media (max-width:760px) {
                #cf_root { padding:8px 6px 16px !important; }
                #cf_sidebar { display:block !important; }
                .cf-frame-shell { height:70vh !important; min-height:540px !important; border-radius:12px !important; }
                .cf-frame-shell iframe { min-height:540px !important; }
                .cf-browser-chip { display:none !important; }
            }
        `;
        document.head.appendChild(style);
    }

    function markLayout() {
        const app = appRoot();
        const frame = app?.querySelector(".cf-frame-shell");
        const connection = app?.querySelector("#cf_connection_card");
        if (!app || !frame || !connection) return false;

        app.dataset.cfRelease = RELEASE_VERSION;

        let common = frame.parentElement;
        while (common && common !== app && !common.contains(connection)) common = common.parentElement;
        if (!common || common === app) {
            const rows = Array.from(app.querySelectorAll(".gradio-row, .row"));
            common = rows.find((row) => row.contains(frame) && row.contains(connection)) || null;
        }
        if (!common) return false;

        if (common.id !== "cf_shell_row") common.id = "cf_shell_row";
        const browserColumn = directChildContaining(common, frame);
        const sidebar = directChildContaining(common, connection);
        if (browserColumn && browserColumn.id !== "cf_browser_column") browserColumn.id = "cf_browser_column";
        if (sidebar && sidebar.id !== "cf_sidebar") sidebar.id = "cf_sidebar";
        return true;
    }

    function enforceCriticalDimensions() {
        const app = appRoot();
        if (!app) return;

        const mark = app.querySelector(".cf-brand-mark");
        const logo = app.querySelector(".cf-brand-mark svg");
        const frame = app.querySelector(".cf-frame-shell");
        const iframe = frame?.querySelector("iframe");

        if (mark) {
            mark.style.cssText += ";width:36px !important;height:36px !important;max-width:36px !important;overflow:hidden !important;";
        }
        if (logo) {
            logo.style.cssText += ";width:30px !important;height:30px !important;max-width:30px !important;max-height:30px !important;";
        }
        if (frame) {
            frame.style.cssText += ";display:block !important;width:100% !important;min-height:640px !important;";
        }
        if (iframe) {
            iframe.setAttribute("width", "100%");
            iframe.setAttribute("height", "100%");
            iframe.style.cssText += ";display:block !important;width:100% !important;height:100% !important;min-height:640px !important;border:0 !important;";
        }
    }

    function syncReleaseIdentity() {
        const app = appRoot();
        if (!app) return;

        const badge = app.querySelector(".cf-version");
        if (badge) {
            badge.textContent = `v${RELEASE_VERSION}`;
            badge.title = "CivitaiFlow stability release";
        }
        const subtitle = app.querySelector(".cf-brand-sub");
        if (subtitle) subtitle.textContent = "Forge-native Civitai workspace · stability-first acquisition";
    }

    function setApiStatus(kind, title, detail) {
        const card = appRoot()?.querySelector("#cf_connection_card");
        const status = card?.querySelector(".cf-status");
        if (!status) return;

        status.className = `cf-status cf-status-${kind}`;
        status.innerHTML = `
            <span class="cf-status-dot" aria-hidden="true"></span>
            <span class="cf-status-copy">
                <strong>${escapeHtml(title)}</strong>
                ${detail ? `<span class="cf-status-detail">${escapeHtml(detail)}</span>` : ""}
            </span>
        `;
    }

    async function syncApiStatus(force) {
        const now = Date.now();
        if (authSyncInFlight) return;
        if (!force && now - lastAuthSyncAt < 30000) return;
        if (!appRoot()?.querySelector("#cf_connection_card")) return;

        authSyncInFlight = true;
        try {
            const response = await fetch(AUTH_STATUS_URL, { cache: "no-store" });
            if (!response.ok) return;
            const data = await response.json();
            lastAuthSyncAt = Date.now();

            if (!data.configured) {
                setApiStatus(
                    "muted",
                    "API access not configured",
                    "Paste a Civitai API key, then click Connect API."
                );
                return;
            }

            if (data.valid === true) {
                setApiStatus(
                    "ok",
                    `Connected as ${data.username || "Civitai user"}`,
                    `API key saved in Forge · ${data.maskedKey || "configured"}`
                );
                return;
            }

            if (data.valid === false) {
                setApiStatus(
                    "error",
                    "Saved API key could not be verified",
                    data.error || "Use Verify or reconnect the API key."
                );
                return;
            }

            setApiStatus(
                "warn",
                "API key saved in Forge",
                `${data.maskedKey || "configured"} · Click Verify to confirm access.`
            );
        } catch (_) {
            // Older checkouts may not expose the status endpoint. The Gradio state remains authoritative.
        } finally {
            authSyncInFlight = false;
        }
    }

    function ensureSystemCard() {
        const app = appRoot();
        const connection = app?.querySelector("#cf_connection_card");
        if (!app || !connection) return;

        let card = app.querySelector(`#${SYSTEM_CARD_ID}`);
        if (!card) {
            card = document.createElement("div");
            card.id = SYSTEM_CARD_ID;
            card.innerHTML = `
                <div class="cf-section-label">Library & lifecycle</div>
                <div class="cf-system-copy">Local inventory, update intelligence and transfer health.</div>
                <div id="${SYSTEM_HOST_ID}"></div>
            `;
            connection.insertAdjacentElement("afterend", card);
        }

        const host = card.querySelector(`#${SYSTEM_HOST_ID}`);
        for (const selector of ["#cf-library-intelligence", "#cf-update-center"]) {
            const widget = app.querySelector(selector);
            if (host && widget && widget.parentElement !== host) host.appendChild(widget);
        }
    }

    function ensureBrowserToolbar() {
        const shell = appRoot()?.querySelector(".cf-frame-shell");
        if (!shell || shell.querySelector(".cf-browser-toolbar")) return;

        const toolbar = document.createElement("div");
        toolbar.className = "cf-browser-toolbar";
        toolbar.innerHTML = `
            <span class="cf-browser-chip">Embedded · best effort</span>
            <button type="button" class="cf-browser-action cf-browser-action-primary" data-cf-action="companion" title="Open Civitai as a normal top-level browser window">${iconExternal()}<span>Companion</span></button>
            <button type="button" class="cf-browser-action" data-cf-action="reload" title="Reload the embedded Civitai panel">${iconReload()}<span>Reload</span></button>
        `;

        toolbar.querySelector('[data-cf-action="companion"]').addEventListener("click", function () {
            const popup = openCompanion(CIVITAI_HOME);
            if (!popup) window.open(CIVITAI_HOME, "_blank", "noopener,noreferrer");
        });
        toolbar.querySelector('[data-cf-action="reload"]').addEventListener("click", reloadEmbeddedPanel);
        shell.appendChild(toolbar);
    }

    function bind() {
        bindQueued = false;
        ensureRuntimeStyles();
        if (!appRoot()) return false;

        markLayout();
        enforceCriticalDimensions();
        syncReleaseIdentity();
        ensureSystemCard();
        ensureBrowserToolbar();

        intercept(
            findButtonByText("Open Civitai in Browser ↗") || findButtonByText("Open Companion Window ↗"),
            CIVITAI_HOME,
            "Open Companion Window ↗",
            "Open Civitai in a top-level browser window. Recommended for login and whenever the embedded page is blank or blocked."
        );
        intercept(
            findButtonByText("Get API Key ↗"),
            CIVITAI_ACCOUNT,
            "Get API Key ↗",
            "Open Civitai Account to create or manage a personal API key."
        );

        void syncApiStatus(false);
        return true;
    }

    function scheduleBind() {
        if (bindQueued) return;
        bindQueued = true;
        window.requestAnimationFrame(bind);
    }

    function bootUntilReady(attempt) {
        scheduleBind();
        if (appRoot() || attempt >= 40) return;
        window.setTimeout(() => bootUntilReady(attempt + 1), 250);
    }

    ensureRuntimeStyles();

    if (typeof onUiLoaded === "function") onUiLoaded(scheduleBind);
    else window.addEventListener("load", scheduleBind, { once: true });

    window.addEventListener("focus", function () {
        scheduleBind();
        void syncApiStatus(true);
    });

    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) {
            scheduleBind();
            void syncApiStatus(false);
        }
    });

    // Finite startup recovery only. Do not attach to onUiUpdate and do not run a permanent
    // one-second DOM repair loop: both patterns can create a mutation/re-render feedback loop
    // in Forge/Gradio and were the primary 22.7.x blank-screen stability risk.
    bootUntilReady(0);
})();
