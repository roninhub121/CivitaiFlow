(function () {
    "use strict";

    const STYLE_ID = "cf-22-8-ux-style";
    const SEND_BUTTON_ID = "cf-send-now";
    const SEND_STATUS_ID = "cf-send-now-status";

    function root() {
        return typeof gradioApp === "function" ? gradioApp() : document;
    }

    function ensureStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            #cf_shell_row {
                grid-template-columns: minmax(390px, 430px) minmax(0, 1fr) !important;
                gap: 14px !important;
            }
            #cf_sidebar { max-width: 430px !important; }
            #cf_connection_card,
            #cf_capture_card,
            #cf_activity_card,
            #cf_system_card {
                padding: 11px !important;
                margin-bottom: 9px !important;
            }
            #cf_root .gradio-row { gap: 7px !important; }
            #cf_root button { min-height: 34px !important; }
            #cf_terminal textarea {
                min-height: 92px !important;
                max-height: 150px !important;
                resize: vertical !important;
            }
            #cf_dropzone textarea {
                min-height: 64px !important;
            }

            #cf_system_card { position: relative !important; }
            #cf_system_card[data-cf-open="0"] #cf_system_host { display: none !important; }
            #cf_system_card[data-cf-open="0"] .cf-system-copy { margin-bottom: 0 !important; }
            .cf-system-toggle {
                position: absolute !important;
                top: 7px !important;
                right: 8px !important;
                min-height: 25px !important;
                height: 25px !important;
                padding: 0 8px !important;
                border-radius: 7px !important;
                border: 1px solid rgba(148,163,184,.18) !important;
                background: rgba(30,41,59,.55) !important;
                color: #cbd5e1 !important;
                font: 650 10px/1 ui-sans-serif,system-ui,sans-serif !important;
            }

            .cf-quick-actions {
                display: grid !important;
                grid-template-columns: minmax(120px, .65fr) minmax(0, 1fr) !important;
                align-items: center !important;
                gap: 8px !important;
                margin: 8px 0 2px !important;
            }
            #${SEND_BUTTON_ID} {
                min-height: 36px !important;
                border-color: rgba(249,115,22,.42) !important;
                background: rgba(249,115,22,.16) !important;
                color: #fed7aa !important;
            }
            #${SEND_BUTTON_ID}:hover { background: rgba(249,115,22,.25) !important; }
            #${SEND_BUTTON_ID}:disabled { opacity: .55 !important; cursor: wait !important; }
            #${SEND_STATUS_ID} {
                min-width: 0 !important;
                color: #94a3b8 !important;
                font: 560 10px/1.35 ui-sans-serif,system-ui,sans-serif !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
            }
            #${SEND_STATUS_ID}[data-state="ok"] { color: #6ee7b7 !important; }
            #${SEND_STATUS_ID}[data-state="error"] { color: #fda4af !important; }
            #${SEND_STATUS_ID}[data-state="busy"] { color: #93c5fd !important; }

            #cf_root .cf-safe-workspace {
                height: calc(100vh - 155px) !important;
                min-height: 520px !important;
                display: grid !important;
                place-items: center !important;
                padding: 28px !important;
                background:
                    radial-gradient(circle at 85% 15%, rgba(249,115,22,.08), transparent 28%),
                    linear-gradient(180deg, rgba(10,15,26,.98), rgba(8,12,20,.98)) !important;
            }
            .cf-safe-workspace-inner {
                width: min(720px, 92%) !important;
                padding: 28px !important;
                border: 1px solid rgba(148,163,184,.16) !important;
                border-radius: 18px !important;
                background: rgba(15,23,42,.52) !important;
                box-shadow: 0 20px 60px rgba(0,0,0,.18) !important;
                color: #dbe4ef !important;
                font-family: ui-sans-serif,system-ui,sans-serif !important;
            }
            .cf-safe-kicker {
                margin-bottom: 9px !important;
                color: #fb923c !important;
                font: 760 10px/1 ui-sans-serif,system-ui,sans-serif !important;
                letter-spacing: .14em !important;
            }
            .cf-safe-workspace-inner h2 {
                margin: 0 0 10px !important;
                color: #f8fafc !important;
                font: 760 25px/1.15 ui-sans-serif,system-ui,sans-serif !important;
                letter-spacing: -.025em !important;
            }
            .cf-safe-workspace-inner p {
                margin: 0 !important;
                color: #94a3b8 !important;
                font: 520 13px/1.6 ui-sans-serif,system-ui,sans-serif !important;
            }
            .cf-safe-grid {
                display: grid !important;
                grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
                gap: 10px !important;
                margin-top: 18px !important;
            }
            .cf-safe-grid > div {
                padding: 13px !important;
                border: 1px solid rgba(148,163,184,.14) !important;
                border-radius: 11px !important;
                background: rgba(2,6,23,.28) !important;
            }
            .cf-safe-grid strong,
            .cf-safe-grid span { display: block !important; }
            .cf-safe-grid strong { margin-bottom: 5px !important; color: #e2e8f0 !important; font-size: 11px !important; }
            .cf-safe-grid span { color: #94a3b8 !important; font-size: 11px !important; line-height: 1.45 !important; }
            .cf-safe-note {
                margin-top: 14px !important;
                color: #64748b !important;
                font-size: 10px !important;
            }

            @media (max-width: 1180px) {
                #cf_shell_row { grid-template-columns: 1fr !important; }
                #cf_sidebar { max-width: none !important; }
            }
            @media (max-width: 760px) {
                .cf-safe-grid { grid-template-columns: 1fr !important; }
                .cf-quick-actions { grid-template-columns: 1fr !important; }
                #cf_root .cf-safe-workspace { min-height: 440px !important; padding: 14px !important; }
                .cf-safe-workspace-inner { padding: 20px !important; }
            }
        `;
        document.head.appendChild(style);
    }

    function extractTargets(value) {
        const text = String(value || "");
        const urls = text.match(/https?:\/\/(?:www\.)?civitai\.com\/models\/\d+[^\s<>'"]*/gi) || [];
        if (urls.length) return [...new Set(urls)];

        const ids = text.split(/\s+/).map((item) => item.trim()).filter((item) => /^\d+(?::\d+)?$/.test(item));
        return [...new Set(ids)];
    }

    async function sendTarget(target) {
        const response = await fetch("/civitaiflow/api/capture", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: target, threads: 5 }),
            cache: "no-store",
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || data.error || `HTTP ${response.status}`);
        return data;
    }

    function captureTextarea() {
        const host = root().querySelector("#cf_dropzone");
        if (!host) return null;
        return host.querySelector("textarea, input") || null;
    }

    function setSendStatus(message, state) {
        const node = root().querySelector(`#${SEND_STATUS_ID}`);
        if (!node) return;
        node.textContent = message;
        node.dataset.state = state || "idle";
    }

    async function sendNow() {
        const button = root().querySelector(`#${SEND_BUTTON_ID}`);
        const textarea = captureTextarea();
        if (!button || !textarea) return;

        let text = textarea.value || "";
        let targets = extractTargets(text);

        if (!targets.length && navigator.clipboard && navigator.clipboard.readText) {
            try {
                text = await navigator.clipboard.readText();
                targets = extractTargets(text);
                if (targets.length) {
                    textarea.value = text;
                    textarea.dispatchEvent(new Event("input", { bubbles: true }));
                }
            } catch (_) {
                // Browser clipboard-read permission is optional. Manual paste still works.
            }
        }

        if (!targets.length) {
            setSendStatus("Paste a civitai.com/models/... link first.", "error");
            return;
        }

        button.disabled = true;
        setSendStatus(`Sending ${targets.length} target${targets.length === 1 ? "" : "s"}…`, "busy");

        let queued = 0;
        let installed = 0;
        let failed = 0;
        for (const target of targets) {
            try {
                const data = await sendTarget(target);
                queued += Number(data.queued || 0);
                if (data.state === "installed") installed += 1;
                if (data.ok === false && data.state !== "indexing") failed += 1;
            } catch (_) {
                failed += 1;
            }
        }

        button.disabled = false;
        if (failed) {
            setSendStatus(`Sent with ${failed} failure${failed === 1 ? "" : "s"}; check Activity.`, "error");
        } else if (queued) {
            setSendStatus(`${queued} queued in Forge.`, "ok");
            textarea.value = "";
            textarea.dispatchEvent(new Event("input", { bubbles: true }));
        } else if (installed) {
            setSendStatus("Already installed locally.", "ok");
        } else {
            setSendStatus("Recognized. Library may still be indexing; check Activity.", "busy");
        }
    }

    function enhanceCapture() {
        const card = root().querySelector("#cf_capture_card");
        const host = root().querySelector("#cf_dropzone");
        if (!card || !host || root().querySelector(`#${SEND_BUTTON_ID}`)) return;

        const actions = document.createElement("div");
        actions.className = "cf-quick-actions";
        actions.innerHTML = `
            <button type="button" id="${SEND_BUTTON_ID}">Send now</button>
            <span id="${SEND_STATUS_ID}">Paste a model URL or copy one with Sniper enabled.</span>
        `;

        const wrapper = host.parentElement || host;
        wrapper.insertAdjacentElement("afterend", actions);
        actions.querySelector(`#${SEND_BUTTON_ID}`).addEventListener("click", () => void sendNow());

        const textarea = captureTextarea();
        if (textarea && textarea.dataset.cfSendBound !== "1") {
            textarea.dataset.cfSendBound = "1";
            textarea.addEventListener("keydown", (event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                    event.preventDefault();
                    void sendNow();
                }
            });
        }
    }

    function enhanceSystemCard() {
        const card = root().querySelector("#cf_system_card");
        if (!card || card.dataset.cfUxBound === "1") return;
        card.dataset.cfUxBound = "1";
        card.dataset.cfOpen = "0";

        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "cf-system-toggle";
        toggle.textContent = "Details";
        toggle.addEventListener("click", () => {
            const open = card.dataset.cfOpen === "1";
            card.dataset.cfOpen = open ? "0" : "1";
            toggle.textContent = open ? "Details" : "Hide";
        });
        card.appendChild(toggle);
    }

    function annotateEmbeddedAction() {
        const buttons = root().querySelectorAll("button");
        for (const button of buttons) {
            if ((button.textContent || "").trim() !== "Reload Panel") continue;
            button.title = "Load the remote Civitai iframe for this session. Experimental: Companion is more stable.";
        }
    }

    function bind() {
        ensureStyles();
        enhanceCapture();
        enhanceSystemCard();
        annotateEmbeddedAction();
    }

    function finiteBoot() {
        const delays = [0, 150, 400, 900, 1800, 3200];
        for (const delay of delays) window.setTimeout(bind, delay);
    }

    ensureStyles();
    if (typeof onUiLoaded === "function") onUiLoaded(finiteBoot);
    else window.addEventListener("load", finiteBoot, { once: true });

    window.addEventListener("focus", bind);
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) bind();
    });
})();
