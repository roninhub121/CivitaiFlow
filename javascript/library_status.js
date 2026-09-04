(function () {
    "use strict";

    const WIDGET_ID = "cf-library-intelligence";
    const STYLE_ID = "cf-library-intelligence-style";

    function root() {
        return typeof gradioApp === "function" ? gradioApp() : document;
    }

    function ensureStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            #${WIDGET_ID} {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                margin-top: 9px;
                padding: 9px 10px;
                border: 1px solid rgba(148, 163, 184, .16);
                border-radius: 9px;
                background: rgba(2, 6, 23, .2);
                color: #94a3b8;
                font: 600 11px/1.3 ui-sans-serif, system-ui, sans-serif;
            }
            #${WIDGET_ID} .cf-library-copy {
                min-width: 0;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            #${WIDGET_ID} .cf-library-dot {
                width: 7px;
                height: 7px;
                flex: 0 0 auto;
                border-radius: 999px;
                background: #64748b;
            }
            #${WIDGET_ID}[data-state="ready"] .cf-library-dot { background: #34d399; }
            #${WIDGET_ID}[data-state="running"] .cf-library-dot { background: #60a5fa; }
            #${WIDGET_ID}[data-state="error"] .cf-library-dot { background: #fb7185; }
            #${WIDGET_ID} .cf-library-text {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            #${WIDGET_ID} .cf-library-reindex {
                appearance: none;
                flex: 0 0 auto;
                min-height: 28px !important;
                padding: 0 8px !important;
                border: 1px solid rgba(148, 163, 184, .2) !important;
                border-radius: 7px !important;
                background: rgba(30, 41, 59, .55) !important;
                color: inherit !important;
                font: 650 10px/1 ui-sans-serif, system-ui, sans-serif !important;
                cursor: pointer;
            }
            #${WIDGET_ID} .cf-library-reindex:hover {
                background: rgba(51, 65, 85, .72) !important;
            }
        `;
        document.head.appendChild(style);
    }

    function widgetHost() {
        return root().querySelector("#cf_system_host") || root().querySelector("#cf_connection_card");
    }

    function ensureWidget() {
        const host = widgetHost();
        if (!host) return null;
        let widget = root().querySelector(`#${WIDGET_ID}`);
        if (widget) {
            if (widget.parentElement !== host) host.appendChild(widget);
            return widget;
        }

        ensureStyles();
        widget = document.createElement("div");
        widget.id = WIDGET_ID;
        widget.dataset.state = "running";
        widget.innerHTML = `
            <div class="cf-library-copy">
                <span class="cf-library-dot" aria-hidden="true"></span>
                <span class="cf-library-text">Library index · connecting…</span>
            </div>
            <button type="button" class="cf-library-reindex" title="Re-scan local Forge model folders and refresh SHA-256 duplicate detection">Reindex</button>
        `;
        widget.querySelector(".cf-library-reindex").addEventListener("click", async () => {
            const button = widget.querySelector(".cf-library-reindex");
            button.disabled = true;
            button.textContent = "Starting…";
            try {
                await fetch("/civitaiflow/api/reindex", { method: "POST", cache: "no-store" });
            } catch (_) {
                // Polling below will expose the service state.
            }
            window.setTimeout(() => {
                button.disabled = false;
                button.textContent = "Reindex";
                void refreshWidget();
            }, 800);
        });
        host.appendChild(widget);
        return widget;
    }

    async function refreshWidget() {
        const widget = ensureWidget();
        if (!widget) return;
        const text = widget.querySelector(".cf-library-text");
        try {
            const response = await fetch("/civitaiflow/api/library", { cache: "no-store" });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (data.error) {
                widget.dataset.state = "error";
                text.textContent = `Library index · ${data.error}`;
                return;
            }
            if (data.running || !data.ready) {
                widget.dataset.state = "running";
                const progress = data.total ? ` · ${data.processed}/${data.total}` : "";
                text.textContent = `Library indexing${progress}`;
                return;
            }
            widget.dataset.state = "ready";
            const loras = Number(data.counts?.LORA || 0);
            const checkpoints = Number(data.counts?.Checkpoint || 0);
            text.textContent = `${Number(data.assets || 0).toLocaleString()} indexed · ${loras.toLocaleString()} LoRA · ${checkpoints.toLocaleString()} checkpoints`;
        } catch (_) {
            widget.dataset.state = "error";
            text.textContent = "Library index · service unavailable · restart Forge after updating CivitaiFlow";
        }
    }

    function bind() {
        ensureWidget();
        void refreshWidget();
    }

    if (typeof onUiLoaded === "function") onUiLoaded(bind);
    if (typeof onUiUpdate === "function") onUiUpdate(bind);
    else window.addEventListener("load", bind, { once: true });

    window.setInterval(refreshWidget, 3000);
})();
