(function () {
    "use strict";

    const RELEASE_VERSION = "22.7.1";
    const STYLE_ID = "cf-premium-shell-style";
    const SYSTEM_CARD_ID = "cf_system_card";
    const SYSTEM_HOST_ID = "cf_system_host";

    function root() {
        return typeof gradioApp === "function" ? gradioApp() : document;
    }

    function directChildContaining(parent, node) {
        if (!parent || !node) return null;
        let current = node;
        while (current && current.parentElement && current.parentElement !== parent) {
            current = current.parentElement;
        }
        return current && current.parentElement === parent ? current : null;
    }

    function markLayout() {
        const app = root().querySelector("#cf_root");
        if (!app) return null;

        app.dataset.cfRelease = RELEASE_VERSION;
        const frame = app.querySelector(".cf-frame-shell");
        if (!frame) return app;

        const shellRow = Array.from(app.querySelectorAll(".gradio-row, .row"))
            .find((row) => row.contains(frame));
        if (shellRow) {
            shellRow.id = "cf_shell_row";
            const browserColumn = directChildContaining(shellRow, frame);
            if (browserColumn) browserColumn.id = "cf_browser_column";

            const sidebar = Array.from(shellRow.children)
                .find((child) => child !== browserColumn && child.querySelector && child.querySelector("#cf_connection_card"));
            if (sidebar) sidebar.id = "cf_sidebar";
        }

        let stage = frame.parentElement;
        while (
            stage &&
            stage.parentElement &&
            stage.parentElement.id !== "cf_browser_column" &&
            !stage.classList.contains("html-container")
        ) {
            stage = stage.parentElement;
        }
        if (stage && stage !== frame) stage.id = "cf_browser_stage";

        return app;
    }

    function ensureSystemCard() {
        const app = root().querySelector("#cf_root");
        const connection = app?.querySelector("#cf_connection_card");
        if (!connection) return null;

        let card = app.querySelector(`#${SYSTEM_CARD_ID}`);
        if (!card) {
            card = document.createElement("div");
            card.id = SYSTEM_CARD_ID;
            card.className = "cf-runtime-card";
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
            if (widget && widget.parentElement !== host) host.appendChild(widget);
        }
        return card;
    }

    function syncReleaseBadge() {
        const badge = root().querySelector("#cf_root .cf-version");
        if (badge && badge.textContent.trim() !== `v${RELEASE_VERSION}`) {
            badge.textContent = `v${RELEASE_VERSION}`;
            badge.title = "CivitaiFlow release";
        }

        const subtitle = root().querySelector("#cf_root .cf-brand-sub");
        if (subtitle && subtitle.textContent.includes("Embedded Civitai")) {
            subtitle.textContent = "Forge-native Civitai workspace · smart acquisition · lifecycle safety";
        }
    }

    function enforceCriticalDimensions() {
        const app = root().querySelector("#cf_root");
        if (!app) return;

        const mark = app.querySelector(".cf-brand-mark");
        const logo = app.querySelector(".cf-brand-mark svg");
        const frame = app.querySelector(".cf-frame-shell");
        const iframe = frame?.querySelector("iframe");

        if (mark) {
            mark.style.setProperty("width", "36px", "important");
            mark.style.setProperty("height", "36px", "important");
            mark.style.setProperty("min-width", "36px", "important");
            mark.style.setProperty("flex", "0 0 36px", "important");
        }
        if (logo) {
            logo.style.setProperty("width", "30px", "important");
            logo.style.setProperty("height", "30px", "important");
            logo.style.setProperty("display", "block", "important");
        }
        if (frame) {
            frame.style.setProperty("width", "100%", "important");
            frame.style.setProperty("min-width", "0", "important");
            frame.style.setProperty("height", "clamp(640px, calc(100vh - 170px), 980px)", "important");
            frame.style.setProperty("min-height", "640px", "important");
        }
        if (iframe) {
            iframe.style.setProperty("display", "block", "important");
            iframe.style.setProperty("width", "100%", "important");
            iframe.style.setProperty("height", "100%", "important");
            iframe.style.setProperty("min-height", "640px", "important");
            iframe.style.setProperty("border", "0", "important");
        }
    }

    function ensureStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            #cf_root {
                --cf-bg: #0b0f18;
                --cf-panel: rgba(15, 23, 42, .58);
                --cf-panel-strong: rgba(15, 23, 42, .82);
                --cf-panel-soft: rgba(2, 6, 23, .30);
                --cf-border: rgba(148, 163, 184, .17);
                --cf-border-strong: rgba(148, 163, 184, .28);
                --cf-text: #e5e7eb;
                --cf-text-dim: #94a3b8;
                --cf-accent: #f97316;
                --cf-ok: #34d399;
                --cf-warn: #fbbf24;
                --cf-error: #fb7185;
                width: 100% !important;
                max-width: none !important;
                min-width: 0 !important;
                box-sizing: border-box !important;
                padding: 10px 12px 18px !important;
                gap: 14px !important;
            }
            #cf_root, #cf_root * { box-sizing: border-box; }
            #cf_root > div,
            #cf_root .contain,
            #cf_root .wrap,
            #cf_root .form { max-width: none !important; }

            #cf_shell_row {
                display: grid !important;
                grid-template-columns: minmax(340px, 410px) minmax(0, 1fr) !important;
                align-items: start !important;
                gap: 16px !important;
                width: 100% !important;
                max-width: none !important;
                min-width: 0 !important;
                flex-wrap: nowrap !important;
            }
            #cf_sidebar {
                width: 100% !important;
                max-width: 410px !important;
                min-width: 0 !important;
                gap: 11px !important;
            }
            #cf_browser_column {
                width: 100% !important;
                max-width: none !important;
                min-width: 0 !important;
                overflow: visible !important;
            }
            #cf_browser_stage,
            #cf_browser_stage > div,
            #cf_browser_stage .prose,
            #cf_browser_stage .html-container,
            #cf_browser_column .html-container,
            #cf_browser_column .prose {
                width: 100% !important;
                max-width: none !important;
                min-width: 0 !important;
                padding: 0 !important;
                margin: 0 !important;
            }

            .cf-brand {
                display: flex !important;
                align-items: center !important;
                gap: 12px !important;
                min-height: 48px !important;
                padding: 4px 4px 10px !important;
                overflow: hidden !important;
            }
            .cf-brand-mark {
                width: 36px !important;
                height: 36px !important;
                min-width: 36px !important;
                flex: 0 0 36px !important;
                display: grid !important;
                place-items: center !important;
                color: var(--cf-accent) !important;
            }
            .cf-brand-mark svg {
                display: block !important;
                width: 30px !important;
                height: 30px !important;
                max-width: 30px !important;
                max-height: 30px !important;
            }
            .cf-brand-row {
                display: flex !important;
                align-items: center !important;
                gap: 9px !important;
                min-width: 0 !important;
                line-height: 1 !important;
            }
            .cf-brand-name {
                color: var(--cf-text) !important;
                font: 760 20px/1 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
                letter-spacing: -.025em !important;
            }
            .cf-version {
                display: inline-flex !important;
                align-items: center !important;
                min-height: 22px !important;
                padding: 0 7px !important;
                border: 1px solid var(--cf-border-strong) !important;
                border-radius: 999px !important;
                background: rgba(148, 163, 184, .06) !important;
                color: var(--cf-text-dim) !important;
                font: 720 10px/1 ui-sans-serif, system-ui, sans-serif !important;
                letter-spacing: .04em !important;
                white-space: nowrap !important;
            }
            .cf-brand-sub {
                margin-top: 6px !important;
                color: var(--cf-text-dim) !important;
                font: 520 11px/1.35 ui-sans-serif, system-ui, sans-serif !important;
            }

            #cf_connection_card,
            #cf_capture_card,
            #cf_activity_card,
            #${SYSTEM_CARD_ID} {
                width: 100% !important;
                min-width: 0 !important;
                margin: 0 0 11px !important;
                padding: 13px !important;
                border: 1px solid var(--cf-border) !important;
                border-radius: 14px !important;
                background: linear-gradient(180deg, rgba(15,23,42,.68), rgba(15,23,42,.48)) !important;
                box-shadow: 0 12px 30px rgba(0, 0, 0, .08) !important;
                overflow: hidden !important;
            }
            #${SYSTEM_CARD_ID} { display: block !important; }
            #${SYSTEM_HOST_ID} { width: 100% !important; min-width: 0 !important; }
            .cf-system-copy {
                margin: -4px 0 7px !important;
                color: var(--cf-text-dim) !important;
                font: 500 11px/1.4 ui-sans-serif, system-ui, sans-serif !important;
            }
            .cf-section-label {
                margin: 0 0 10px !important;
                color: var(--cf-text-dim) !important;
                font: 760 10px/1 ui-sans-serif, system-ui, sans-serif !important;
                letter-spacing: .12em !important;
                text-transform: uppercase !important;
            }
            .cf-status {
                display: flex !important;
                align-items: center !important;
                gap: 9px !important;
                min-height: 44px !important;
                margin: 0 0 10px !important;
                padding: 9px 11px !important;
                border: 1px solid var(--cf-border) !important;
                border-radius: 10px !important;
                background: var(--cf-panel-soft) !important;
            }
            .cf-status-dot {
                width: 8px !important;
                height: 8px !important;
                flex: 0 0 8px !important;
                border-radius: 999px !important;
                background: var(--cf-text-dim) !important;
                box-shadow: 0 0 0 4px rgba(148, 163, 184, .08) !important;
            }
            .cf-status-ok .cf-status-dot { background: var(--cf-ok) !important; box-shadow: 0 0 0 4px rgba(52,211,153,.10) !important; }
            .cf-status-warn .cf-status-dot { background: var(--cf-warn) !important; box-shadow: 0 0 0 4px rgba(251,191,36,.10) !important; }
            .cf-status-error .cf-status-dot { background: var(--cf-error) !important; box-shadow: 0 0 0 4px rgba(251,113,133,.10) !important; }
            .cf-status-copy {
                display: flex !important;
                flex-direction: column !important;
                min-width: 0 !important;
                color: var(--cf-text) !important;
                line-height: 1.25 !important;
            }
            .cf-status-copy strong { font-size: 12px !important; }
            .cf-status-detail {
                margin-top: 3px !important;
                color: var(--cf-text-dim) !important;
                font-size: 11px !important;
                white-space: normal !important;
            }
            .cf-help {
                padding: 4px 2px !important;
                color: var(--cf-text-dim) !important;
                font: 500 11px/1.5 ui-sans-serif, system-ui, sans-serif !important;
            }
            .cf-help ol { margin: 8px 0 0 18px !important; padding: 0 !important; }

            #cf_root button {
                min-height: 38px !important;
                border-radius: 9px !important;
                font-weight: 650 !important;
                box-shadow: none !important;
            }
            #cf_root button.primary,
            #cf_btn_connect {
                border-color: rgba(249, 115, 22, .38) !important;
                box-shadow: none !important;
            }
            #cf_api_key textarea,
            #cf_api_key input {
                font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
                letter-spacing: .03em !important;
            }
            #cf_dropzone textarea {
                background: rgba(2, 6, 23, .28) !important;
                border: 1px dashed var(--cf-border-strong) !important;
                border-radius: 10px !important;
                text-align: left !important;
            }
            #cf_terminal textarea {
                min-height: 180px !important;
                background: rgba(2, 6, 23, .72) !important;
                color: #cbd5e1 !important;
                border: 1px solid var(--cf-border) !important;
                border-radius: 10px !important;
                box-shadow: none !important;
                font: 500 11px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
            }
            #cf_action_status {
                min-height: 18px !important;
                color: var(--cf-text-dim) !important;
                font-size: 11px !important;
            }

            .cf-frame-shell {
                position: relative !important;
                display: block !important;
                width: 100% !important;
                max-width: none !important;
                min-width: 0 !important;
                height: clamp(640px, calc(100vh - 170px), 980px) !important;
                min-height: 640px !important;
                overflow: hidden !important;
                border: 1px solid var(--cf-border) !important;
                border-radius: 15px !important;
                background: #0b0f19 !important;
                box-shadow: 0 16px 42px rgba(0, 0, 0, .18) !important;
            }
            .cf-frame-shell iframe {
                display: block !important;
                width: 100% !important;
                max-width: none !important;
                height: 100% !important;
                min-height: 640px !important;
                border: 0 !important;
                background: #0b0f19 !important;
            }
            .cf-browser-toolbar {
                top: 10px !important;
                right: 10px !important;
                border-radius: 10px !important;
            }

            @media (max-width: 1180px) {
                #cf_shell_row {
                    grid-template-columns: 1fr !important;
                    display: grid !important;
                }
                #cf_sidebar {
                    max-width: none !important;
                    display: grid !important;
                    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
                    gap: 11px !important;
                }
                #cf_sidebar > :first-child { grid-column: 1 / -1 !important; }
                #cf_activity_card { grid-column: 1 / -1 !important; }
                .cf-frame-shell,
                .cf-frame-shell iframe {
                    min-height: 620px !important;
                }
                .cf-frame-shell { height: 76vh !important; }
            }
            @media (max-width: 760px) {
                #cf_root { padding: 8px 6px 16px !important; }
                #cf_sidebar { display: block !important; }
                .cf-frame-shell,
                .cf-frame-shell iframe { min-height: 540px !important; }
                .cf-frame-shell { height: 70vh !important; border-radius: 12px !important; }
                .cf-browser-chip { display: none !important; }
                .cf-browser-toolbar { max-width: calc(100% - 16px) !important; }
            }
        `;
        document.head.appendChild(style);
    }

    function heal() {
        ensureStyles();
        markLayout();
        ensureSystemCard();
        syncReleaseBadge();
        enforceCriticalDimensions();
    }

    ensureStyles();
    if (typeof onUiLoaded === "function") onUiLoaded(heal);
    if (typeof onUiUpdate === "function") onUiUpdate(heal);
    else window.addEventListener("load", heal, { once: true });

    const observer = new MutationObserver(() => heal());
    window.addEventListener("load", () => {
        const app = root().querySelector("#cf_root");
        if (app) observer.observe(app, { childList: true, subtree: true, characterData: true });
    }, { once: true });

    window.setInterval(heal, 2500);
})();
