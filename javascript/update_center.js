(function () {
    "use strict";

    const WIDGET_ID = "cf-update-center";
    const STYLE_ID = "cf-update-center-style";
    const POLL_MS = 9000;

    function root() {
        return typeof gradioApp === "function" ? gradioApp() : document;
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = String(text);
        return node;
    }

    function ensureStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            #${WIDGET_ID} {
                margin-top: 8px;
                border: 1px solid rgba(148, 163, 184, .16);
                border-radius: 10px;
                background: rgba(2, 6, 23, .24);
                color: #cbd5e1;
                overflow: hidden;
                font: 600 11px/1.35 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }
            #${WIDGET_ID} .cf-update-head {
                min-height: 38px;
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 7px 9px;
            }
            #${WIDGET_ID} .cf-update-dot {
                width: 7px;
                height: 7px;
                flex: 0 0 auto;
                border-radius: 999px;
                background: #64748b;
            }
            #${WIDGET_ID}[data-state="ready"] .cf-update-dot { background: #34d399; }
            #${WIDGET_ID}[data-state="updates"] .cf-update-dot { background: #f59e0b; }
            #${WIDGET_ID}[data-state="running"] .cf-update-dot { background: #60a5fa; }
            #${WIDGET_ID}[data-state="error"] .cf-update-dot { background: #fb7185; }
            #${WIDGET_ID} .cf-update-copy {
                min-width: 0;
                flex: 1 1 auto;
            }
            #${WIDGET_ID} .cf-update-title {
                color: #e2e8f0;
                font-weight: 750;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            #${WIDGET_ID} .cf-update-subtitle {
                margin-top: 2px;
                color: #94a3b8;
                font-weight: 520;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            #${WIDGET_ID} .cf-update-actions {
                display: flex;
                gap: 5px;
                flex: 0 0 auto;
            }
            #${WIDGET_ID} button {
                appearance: none;
                min-height: 27px !important;
                padding: 0 8px !important;
                border: 1px solid rgba(148, 163, 184, .2) !important;
                border-radius: 7px !important;
                background: rgba(30, 41, 59, .62) !important;
                color: #cbd5e1 !important;
                font: 650 10px/1 ui-sans-serif, system-ui, sans-serif !important;
                cursor: pointer;
            }
            #${WIDGET_ID} button:hover:not(:disabled) {
                background: rgba(51, 65, 85, .82) !important;
            }
            #${WIDGET_ID} button:disabled {
                opacity: .48;
                cursor: default;
            }
            #${WIDGET_ID} .cf-update-primary {
                border-color: rgba(245, 158, 11, .32) !important;
                background: rgba(146, 64, 14, .33) !important;
                color: #fde68a !important;
            }
            #${WIDGET_ID} .cf-update-list {
                display: none;
                max-height: 320px;
                overflow: auto;
                border-top: 1px solid rgba(148, 163, 184, .12);
                padding: 5px;
            }
            #${WIDGET_ID}[data-open="1"] .cf-update-list { display: block; }
            #${WIDGET_ID} .cf-update-row {
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto;
                gap: 9px;
                align-items: center;
                padding: 8px;
                border-radius: 8px;
            }
            #${WIDGET_ID} .cf-update-row + .cf-update-row {
                border-top: 1px solid rgba(148, 163, 184, .08);
            }
            #${WIDGET_ID} .cf-update-row:hover {
                background: rgba(30, 41, 59, .32);
            }
            #${WIDGET_ID} .cf-update-model {
                min-width: 0;
            }
            #${WIDGET_ID} .cf-update-name {
                color: #e2e8f0;
                font-weight: 700;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            #${WIDGET_ID} .cf-update-meta {
                margin-top: 3px;
                color: #94a3b8;
                font-weight: 500;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            #${WIDGET_ID} .cf-update-kind {
                display: inline-flex;
                margin-right: 5px;
                padding: 1px 5px;
                border-radius: 999px;
                background: rgba(100, 116, 139, .18);
                color: #cbd5e1;
                font-size: 9px;
                font-weight: 750;
                letter-spacing: .02em;
                text-transform: uppercase;
            }
            #${WIDGET_ID} .cf-update-empty {
                padding: 13px 10px;
                color: #94a3b8;
                text-align: center;
                font-weight: 520;
            }
        `;
        document.head.appendChild(style);
    }

    function ensureWidget() {
        const card = root().querySelector("#cf_connection_card");
        if (!card) return null;
        let widget = root().querySelector(`#${WIDGET_ID}`);
        if (widget) return widget;

        ensureStyles();
        widget = el("div");
        widget.id = WIDGET_ID;
        widget.dataset.state = "running";
        widget.dataset.open = "0";

        const head = el("div", "cf-update-head");
        const dot = el("span", "cf-update-dot");
        const copy = el("div", "cf-update-copy");
        const title = el("div", "cf-update-title", "Model updates · connecting…");
        const subtitle = el("div", "cf-update-subtitle", "Checking local update service");
        copy.append(title, subtitle);

        const actions = el("div", "cf-update-actions");
        const review = el("button", "cf-update-review", "Review");
        const scan = el("button", "cf-update-scan", "Scan");
        const all = el("button", "cf-update-primary cf-update-all", "Update all");
        actions.append(review, scan, all);
        head.append(dot, copy, actions);

        const list = el("div", "cf-update-list");
        widget.append(head, list);
        card.appendChild(widget);

        review.addEventListener("click", () => {
            widget.dataset.open = widget.dataset.open === "1" ? "0" : "1";
            review.textContent = widget.dataset.open === "1" ? "Hide" : "Review";
        });

        scan.addEventListener("click", async () => {
            scan.disabled = true;
            scan.textContent = "Scanning…";
            try {
                await fetch("/civitaiflow/api/updates/scan", { method: "POST", cache: "no-store" });
            } catch (_) {
                // Polling will surface the service state.
            }
            window.setTimeout(() => {
                scan.disabled = false;
                scan.textContent = "Scan";
                void refreshWidget();
            }, 900);
        });

        all.addEventListener("click", async () => {
            const count = Number(widget.dataset.available || 0);
            if (!count) return;
            const ok = window.confirm(
                `Download the latest version for ${count} model${count === 1 ? "" : "s"}? Existing versions will be kept.`
            );
            if (!ok) return;
            all.disabled = true;
            all.textContent = "Queueing…";
            try {
                await fetch("/civitaiflow/api/updates/apply-all", { method: "POST", cache: "no-store" });
            } catch (_) {
                // Polling will update states.
            }
            window.setTimeout(() => {
                all.disabled = false;
                all.textContent = "Update all";
                void refreshWidget();
            }, 1000);
        });

        return widget;
    }

    function renderRows(widget, updates) {
        const list = widget.querySelector(".cf-update-list");
        list.replaceChildren();
        if (!updates.length) {
            list.appendChild(el("div", "cf-update-empty", "No newer Civitai versions are currently known for the indexed library."));
            return;
        }

        for (const item of updates) {
            const row = el("div", "cf-update-row");
            const model = el("div", "cf-update-model");
            const name = el("div", "cf-update-name", item.modelName || `Model ${item.modelId}`);
            const meta = el("div", "cf-update-meta");
            const kind = el("span", "cf-update-kind", item.modelType || "Model");
            const installed = Array.isArray(item.installedVersionIds) && item.installedVersionIds.length
                ? item.installedVersionIds.join(", ")
                : "unknown";
            const suffix = item.state === "downloading" && item.progress !== undefined && item.progress !== null
                ? ` · ${Number(item.progress).toFixed(0)}%`
                : "";
            meta.append(kind, document.createTextNode(`local ${installed} → ${item.latestVersionName || item.latestVersionId}${suffix}`));
            model.append(name, meta);

            const button = el("button", "cf-update-one", item.state === "downloading" ? "Downloading" : item.state === "queued" ? "Queued" : "Update");
            button.disabled = item.state === "downloading" || item.state === "queued" || item.state === "verifying";
            button.addEventListener("click", async () => {
                button.disabled = true;
                button.textContent = "Queueing…";
                try {
                    await fetch("/civitaiflow/api/updates/apply", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ modelId: item.modelId }),
                        cache: "no-store",
                    });
                } catch (_) {
                    button.textContent = "Retry";
                    button.disabled = false;
                    return;
                }
                window.setTimeout(() => void refreshWidget(), 750);
            });

            row.append(model, button);
            list.appendChild(row);
        }
    }

    function ageLabel(timestamp) {
        if (!timestamp) return "never checked";
        const delta = Math.max(0, Date.now() / 1000 - Number(timestamp));
        if (delta < 60) return "checked just now";
        if (delta < 3600) return `checked ${Math.floor(delta / 60)}m ago`;
        if (delta < 86400) return `checked ${Math.floor(delta / 3600)}h ago`;
        return `checked ${Math.floor(delta / 86400)}d ago`;
    }

    async function refreshWidget() {
        const widget = ensureWidget();
        if (!widget) return;
        const title = widget.querySelector(".cf-update-title");
        const subtitle = widget.querySelector(".cf-update-subtitle");
        const scan = widget.querySelector(".cf-update-scan");
        const all = widget.querySelector(".cf-update-all");

        try {
            const response = await fetch("/civitaiflow/api/updates", { cache: "no-store" });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            const available = Number(data.available || 0);
            widget.dataset.available = String(available);

            if (data.running) {
                widget.dataset.state = "running";
                title.textContent = `Model updates · scanning ${Number(data.checked || 0)}/${Number(data.total || 0)}`;
            } else if (available > 0) {
                widget.dataset.state = "updates";
                title.textContent = `Model updates · ${available} available`;
            } else {
                widget.dataset.state = "ready";
                title.textContent = "Model updates · library is current";
            }

            subtitle.textContent = `${data.mode || "Notify only"} · ${ageLabel(data.lastScan)} · every ${Number(data.intervalHours || 24)}h`;
            scan.disabled = Boolean(data.running);
            scan.textContent = data.running ? "Scanning…" : "Scan";
            all.disabled = Boolean(data.running) || available === 0;
            renderRows(widget, Array.isArray(data.updates) ? data.updates : []);

            const badge = root().querySelector(".cf-version-badge");
            if (badge) badge.textContent = "v22.6";
        } catch (_) {
            widget.dataset.state = "error";
            title.textContent = "Model updates · service unavailable";
            subtitle.textContent = "Restart Forge after updating CivitaiFlow.";
            all.disabled = true;
        }
    }

    function bind() {
        ensureWidget();
        void refreshWidget();
    }

    if (typeof onUiLoaded === "function") onUiLoaded(bind);
    if (typeof onUiUpdate === "function") onUiUpdate(bind);
    else window.addEventListener("load", bind, { once: true });

    window.setInterval(refreshWidget, POLL_MS);
})();
