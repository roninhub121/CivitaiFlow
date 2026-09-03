(function () {
    "use strict";

    const CIVITAI_HOME = "https://civitai.com";
    const CIVITAI_ACCOUNT = "https://civitai.com/user/account";
    const COMPANION_NAME = "civitaiflow-companion";
    let companionWindow = null;
    let closeWatcher = null;

    function root() {
        return typeof gradioApp === "function" ? gradioApp() : document;
    }

    function findButtonByText(label) {
        const buttons = root().querySelectorAll("button");
        for (const button of buttons) {
            if ((button.textContent || "").trim() === label) return button;
        }
        return null;
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
                // Reloading is best-effort: a browser may still block third-party
                // cookies or Civitai may refuse framing entirely.
                window.setTimeout(reloadEmbeddedPanel, 250);
            }
        }, 700);
    }

    function openCompanion(url) {
        const width = Math.min(1380, Math.max(980, Math.floor(window.screen.availWidth * 0.78)));
        const height = Math.min(980, Math.max(720, Math.floor(window.screen.availHeight * 0.86)));
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

            // Open a same-browser top-level window. This avoids Google's embedded
            // user-agent restriction and reuses the user's normal browser profile.
            const popup = window.open("about:blank", COMPANION_NAME, features);
            if (!popup) return null;

            try {
                popup.opener = null;
            } catch (_) {
                // Non-fatal; opener hardening is best effort across browsers.
            }
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
                // The existing Python callbacks use webbrowser.open(), which opens
                // on the host machine. A browser-side top-level window uses the
                // user's actual browser profile and also works for remote Forge UIs.
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

    function ensureToolbarStyles() {
        if (document.getElementById("cf-browser-toolbar-style")) return;
        const style = document.createElement("style");
        style.id = "cf-browser-toolbar-style";
        style.textContent = `
            .cf-frame-shell { position: relative !important; }
            .cf-browser-toolbar {
                position: absolute;
                top: 12px;
                right: 12px;
                z-index: 50;
                display: flex;
                align-items: center;
                gap: 7px;
                padding: 6px;
                border: 1px solid rgba(148, 163, 184, .22);
                border-radius: 11px;
                background: rgba(8, 12, 20, .86);
                box-shadow: 0 8px 24px rgba(0, 0, 0, .24);
                backdrop-filter: blur(12px);
            }
            .cf-browser-chip {
                padding: 0 6px;
                color: #94a3b8;
                font: 650 10px/30px ui-sans-serif, system-ui, sans-serif;
                letter-spacing: .06em;
                text-transform: uppercase;
                white-space: nowrap;
            }
            .cf-browser-action {
                appearance: none;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                height: 30px;
                padding: 0 9px;
                border: 1px solid rgba(148, 163, 184, .22);
                border-radius: 8px;
                background: rgba(30, 41, 59, .72);
                color: #e2e8f0;
                font: 650 11px/1 ui-sans-serif, system-ui, sans-serif;
                cursor: pointer;
            }
            .cf-browser-action:hover {
                background: rgba(51, 65, 85, .92);
                border-color: rgba(148, 163, 184, .34);
            }
            .cf-browser-action svg {
                width: 14px;
                height: 14px;
                fill: none;
                stroke: currentColor;
                stroke-width: 1.7;
                stroke-linecap: round;
                stroke-linejoin: round;
            }
            .cf-browser-action-primary {
                border-color: rgba(249, 115, 22, .42);
                background: rgba(249, 115, 22, .14);
            }
            .cf-browser-action-primary:hover {
                background: rgba(249, 115, 22, .22);
                border-color: rgba(249, 115, 22, .58);
            }
        `;
        document.head.appendChild(style);
    }

    function ensureBrowserToolbar() {
        const shell = root().querySelector(".cf-frame-shell");
        if (!shell || shell.querySelector(".cf-browser-toolbar")) return;
        ensureToolbarStyles();

        const toolbar = document.createElement("div");
        toolbar.className = "cf-browser-toolbar";
        toolbar.innerHTML = `
            <span class="cf-browser-chip">Embedded view</span>
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
        intercept(
            findButtonByText("Open Civitai in Browser ↗") || findButtonByText("Open Companion Window ↗"),
            CIVITAI_HOME,
            "Open Companion Window ↗",
            "Open Civitai as a top-level window in this browser. Recommended for login and as a fallback when embedding is blocked."
        );

        intercept(
            findButtonByText("Get API Key ↗"),
            CIVITAI_ACCOUNT,
            "Get API Key ↗",
            "Open Civitai Account in this browser to create or manage a personal API key."
        );

        ensureBrowserToolbar();
    }

    if (typeof onUiLoaded === "function") onUiLoaded(bind);
    if (typeof onUiUpdate === "function") onUiUpdate(bind);
    else window.addEventListener("load", bind, { once: true });
})();
