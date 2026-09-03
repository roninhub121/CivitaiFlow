(function () {
    "use strict";

    const WIDGET_ID = "cf-update-center";
    const STYLE_ID = "cf-update-center-style";
    const POLL_MS = 8000;

    function root() {
        return typeof gradioApp === "function" ? gradioApp() : document;
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = String(text);
        return node;
    }

    function formatBytes(value) {
        const bytes = Number(value || 0);
        if (!bytes) return "0 B";
        const units = ["B", "KB", "MB", "GB", "TB"];
        let size = bytes;
        let index = 0;
        while (size >= 1024 && index < units.length - 1) {
            size /= 1024;
            index += 1;
        }
        return `${size.toFixed(index >= 3 ? 1 : 0)} ${units[index]}`;
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload || {}),
            cache: "no-store",
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    }

    function ensureStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            #${WIDGET_ID} {
                margin-top: 8px;
                border: 1px solid rgba(148, 163, 184, .16);
                border-radius: 11px;
                background: rgba(2, 6, 23, .25);
                color: #cbd5e1;
                overflow: hidden;
                font: 600 11px/1.35 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }
            #${WIDGET_ID} .cf-update-head {
                min-height: 42px;
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 8px 9px;
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
            #${WIDGET_ID} .cf-update-copy { min-width: 0; flex: 1 1 auto; }
            #${WIDGET_ID} .cf-update-title {
                color: #e2e8f0;
                font-weight: 760;
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
            #${WIDGET_ID} .cf-update-actions,
            #${WIDGET_ID} .cf-update-row-actions {
                display: flex;
                gap: 5px;
                flex: 0 0 auto;
                flex-wrap: wrap;
                justify-content: flex-end;
            }
            #${WIDGET_ID} button,
            #${WIDGET_ID} .cf-update-link {
                appearance: none;
                min-height: 27px !important;
                padding: 0 8px !important;
                border: 1px solid rgba(148, 163, 184, .2) !important;
                border-radius: 7px !important;
                background: rgba(30, 41, 59, .62) !important;
                color: #cbd5e1 !important;
                font: 650 10px/27px ui-sans-serif, system-ui, sans-serif !important;
                text-decoration: none !important;
                cursor: pointer;
            }
            #${WIDGET_ID} button:hover:not(:disabled),
            #${WIDGET_ID} .cf-update-link:hover { background: rgba(51, 65, 85, .82) !important; }
            #${WIDGET_ID} button:disabled { opacity: .45; cursor: default; }
            #${WIDGET_ID} .cf-update-primary {
                border-color: rgba(245, 158, 11, .34) !important;
                background: rgba(146, 64, 14, .33) !important;
                color: #fde68a !important;
            }
            #${WIDGET_ID} .cf-update-danger {
                border-color: rgba(244, 63, 94, .24) !important;
                color: #fecdd3 !important;
            }
            #${WIDGET_ID} .cf-update-pin[data-active="1"] {
                border-color: rgba(96, 165, 250, .3) !important;
                background: rgba(30, 64, 175, .25) !important;
                color: #bfdbfe !important;
            }
            #${WIDGET_ID} .cf-update-list {
                display: none;
                max-height: 430px;
                overflow: auto;
                border-top: 1px solid rgba(148, 163, 184, .12);
                padding: 5px;
            }
            #${WIDGET_ID}[data-open="1"] .cf-update-list { display: block; }
            #${WIDGET_ID} .cf-update-row {
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto;
                gap: 10px;
                align-items: start;
                padding: 9px;
                border-radius: 9px;
            }
            #${WIDGET_ID} .cf-update-row + .cf-update-row { border-top: 1px solid rgba(148, 163, 184, .08); }
            #${WIDGET_ID} .cf-update-row:hover { background: rgba(30, 41, 59, .3); }
            #${WIDGET_ID} .cf-update-model { min-width: 0; }
            #${WIDGET_ID} .cf-update-name {
                display: flex;
                gap: 6px;
                align-items: center;
                color: #e2e8f0;
                font-weight: 720;
                min-width: 0;
            }
            #${WIDGET_ID} .cf-update-name-text {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            #${WIDGET_ID} .cf-update-meta {
                margin-top: 3px;
                color: #94a3b8;
                font-weight: 500;
            }
            #${WIDGET_ID} .cf-update-kind,
            #${WIDGET_ID} .cf-update-badge {
                display: inline-flex;
                margin-right: 5px;
                padding: 1px 5px;
                border-radius: 999px;
                background: rgba(100, 116, 139, .18);
                color: #cbd5e1;
                font-size: 9px;
                font-weight: 760;
                letter-spacing: .02em;
                text-transform: uppercase;
            }
            #${WIDGET_ID} .cf-update-badge-pin { background: rgba(30, 64, 175, .28); color: #bfdbfe; }
            #${WIDGET_ID} .cf-update-badge-space { background: rgba(159, 18, 57, .28); color: #fecdd3; }
            #${WIDGET_ID} .cf-update-notes {
                display: none;
                margin-top: 7px;
                padding: 8px 9px;
                border-radius: 8px;
                border: 1px solid rgba(148, 163, 184, .12);
                background: rgba(15, 23, 42, .46);
                color: #cbd5e1;
                font-weight: 480;
                white-space: pre-wrap;
            }
            #${WIDGET_ID} .cf-update-row[data-notes="1"] .cf-update-notes { display: block; }
            #${WIDGET_ID} .cf-update-empty {
                padding: 14px 10px;
                color: #94a3b8;
                text-align: center;
                font-weight: 520;
            }
            @media (max-width: 900px) {
                #${WIDGET_ID} .cf-update-head { align-items: flex-start; flex-wrap: wrap; }
                #${WIDGET_ID} .cf-update-actions { width: 100%; justify-content: flex-start; }
                #${WIDGET_ID} .cf-update-row { grid-template-columns: 1fr; }
                #${WIDGET_ID} .cf-update-row-actions { justify-content: flex-start; }
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
        const title = el("div", "cf-update-title", "Model lifecycle · connecting…");
        const subtitle = el("div", "cf-update-subtitle", "Update intelligence, queue and disk safety");
        copy.append(title, subtitle);

        const actions = el("div", "cf-update-actions");
        const review = el("button", "cf-update-review", "Review");
        const scan = el("button", "cf-update-scan", "Scan");
        const resume = el("button", "cf-update-resume", "Resume");
        const all = el("button", "cf-update-primary cf-update-all", "Update all");
        actions.append(review, scan, resume, all);
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
            try { await fetch("/civitaiflow/api/updates/scan", { method: "POST", cache: "no-store" }); } catch (_) {}
            window.setTimeout(() => void refreshWidget(), 700);
        });

        resume.addEventListener("click", async () => {
            resume.disabled = true;
            resume.textContent = "Resuming…";
            try { await fetch("/civitaiflow/api/queue/resume", { method: "POST", cache: "no-store" }); } catch (_) {}
            window.setTimeout(() => void refreshWidget(), 700);
        });

        all.addEventListener("click", async () => {
            const count = Number(widget.dataset.available || 0);
            if (!count) return;
            const total = Number(widget.dataset.downloadBytes || 0);
            const free = Number(widget.dataset.diskFreeBytes || 0);
            const reserve = Number(widget.dataset.reserveBytes || 0);
            const copyText = [
                `Download the latest version for ${count} model${count === 1 ? "" : "s"}?`,
                total ? `Estimated download: ${formatBytes(total)}.` : "",
                free ? `Free disk: ${formatBytes(free)} (reserve: ${formatBytes(reserve)}).` : "",
                "Existing versions will be kept. Models without enough disk space will be skipped.",
            ].filter(Boolean).join("\n");
            if (!window.confirm(copyText)) return;
            all.disabled = true;
            all.textContent = "Queueing…";
            try { await fetch("/civitaiflow/api/updates/apply-all", { method: "POST", cache: "no-store" }); } catch (_) {}
            window.setTimeout(() => void refreshWidget(), 900);
        });

        return widget;
    }

    async function setPolicy(item, action, versionId) {
        return postJson("/civitaiflow/api/policy", {
            modelId: item.modelId,
            modelVersionId: versionId || null,
            action,
        });
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
            row.dataset.notes = "0";
            const model = el("div", "cf-update-model");
            const name = el("div", "cf-update-name");
            const nameText = el("span", "cf-update-name-text", item.modelName || `Model ${item.modelId}`);
            name.appendChild(nameText);
            if (item.pinned) name.appendChild(el("span", "cf-update-badge cf-update-badge-pin", "Pinned"));
            if (item.diskSpaceOk === false) name.appendChild(el("span", "cf-update-badge cf-update-badge-space", "Low disk"));

            const meta = el("div", "cf-update-meta");
            const kind = el("span", "cf-update-kind", item.modelType || "Model");
            const installed = Array.isArray(item.installedVersionIds) && item.installedVersionIds.length ? item.installedVersionIds.join(", ") : "unknown";
            const progress = item.state === "downloading" && item.progress !== undefined && item.progress !== null ? ` · ${Number(item.progress).toFixed(0)}%` : "";
            const size = item.sizeBytes ? ` · ${formatBytes(item.sizeBytes)}` : "";
            const base = item.baseModel ? ` · ${item.baseModel}` : "";
            meta.append(kind, document.createTextNode(`local ${installed} → ${item.latestVersionName || item.latestVersionId}${base}${size}${progress}`));

            const notes = el("div", "cf-update-notes", item.releaseNotes || "No version-specific release notes were returned by the Civitai model API.");
            model.append(name, meta, notes);

            const actions = el("div", "cf-update-row-actions");
            const notesButton = el("button", "cf-update-notes-toggle", "Notes");
            const pin = el("button", "cf-update-pin", item.pinned ? "Unpin" : "Pin");
            pin.dataset.active = item.pinned ? "1" : "0";
            const ignore = el("button", "cf-update-danger cf-update-ignore", "Ignore");
            const open = el("a", "cf-update-link", "Civitai ↗");
            open.href = item.url || `https://civitai.com/models/${item.modelId}`;
            open.target = "_blank";
            open.rel = "noopener noreferrer";
            const update = el("button", "cf-update-primary cf-update-one",
                item.state === "downloading" ? "Downloading" :
                item.state === "queued" ? "Queued" :
                item.state === "verifying" ? "Verifying" : "Update");
            update.disabled = item.state === "downloading" || item.state === "queued" || item.state === "verifying" || item.diskSpaceOk === false;

            notesButton.addEventListener("click", () => {
                row.dataset.notes = row.dataset.notes === "1" ? "0" : "1";
                notesButton.textContent = row.dataset.notes === "1" ? "Hide notes" : "Notes";
            });

            pin.addEventListener("click", async () => {
                pin.disabled = true;
                pin.textContent = item.pinned ? "Unpinning…" : "Pinning…";
                const installedVersion = Array.isArray(item.installedVersionIds) && item.installedVersionIds.length ? item.installedVersionIds[item.installedVersionIds.length - 1] : null;
                try { await setPolicy(item, item.pinned ? "unpin" : "pin", installedVersion); } catch (_) {}
                window.setTimeout(() => void refreshWidget(), 500);
            });

            ignore.addEventListener("click", async () => {
                if (!window.confirm(`Ignore Civitai version ${item.latestVersionName || item.latestVersionId} for ${item.modelName || item.modelId}? A later version can appear again on future scans.`)) return;
                ignore.disabled = true;
                ignore.textContent = "Ignoring…";
                try { await setPolicy(item, "ignore", item.latestVersionId); } catch (_) {}
                window.setTimeout(() => void refreshWidget(), 500);
            });

            update.addEventListener("click", async () => {
                update.disabled = true;
                update.textContent = "Queueing…";
                try { await postJson("/civitaiflow/api/updates/apply", { modelId: item.modelId }); }
                catch (_) {
                    update.textContent = "Retry";
                    update.disabled = false;
                    return;
                }
                window.setTimeout(() => void refreshWidget(), 650);
            });

            actions.append(notesButton, pin, ignore, open, update);
            row.append(model, actions);
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
        const resume = widget.querySelector(".cf-update-resume");
        const all = widget.querySelector(".cf-update-all");

        try {
            const response = await fetch("/civitaiflow/api/updates", { cache: "no-store" });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            const available = Number(data.available || 0);
            const queue = data.queue || {};
            const resumable = Number(queue.resumable || 0);
            widget.dataset.available = String(available);
            widget.dataset.downloadBytes = String(Number(data.downloadBytes || 0));
            widget.dataset.diskFreeBytes = String(Number(data.diskFreeBytes || 0));
            widget.dataset.reserveBytes = String(Number(data.reserveBytes || 0));

            if (data.running) {
                widget.dataset.state = "running";
                title.textContent = `Model lifecycle · scanning ${Number(data.checked || 0)}/${Number(data.total || 0)}`;
            } else if (available > 0) {
                widget.dataset.state = "updates";
                title.textContent = `Model lifecycle · ${available} update${available === 1 ? "" : "s"} available`;
            } else {
                widget.dataset.state = "ready";
                title.textContent = "Model lifecycle · library is current";
            }

            const size = Number(data.downloadBytes || 0) ? ` · ${formatBytes(data.downloadBytes)} pending` : "";
            const free = Number(data.diskFreeBytes || 0) ? ` · ${formatBytes(data.diskFreeBytes)} free` : "";
            const resumeText = resumable ? ` · ${resumable} resumable` : "";
            subtitle.textContent = `${data.mode || "Notify only"} · ${ageLabel(data.lastScan)} · every ${Number(data.intervalHours || 24)}h${size}${free}${resumeText}`;

            scan.disabled = Boolean(data.running);
            scan.textContent = data.running ? "Scanning…" : "Scan";
            resume.disabled = resumable === 0;
            resume.textContent = resumable ? `Resume ${resumable}` : "Resume";
            all.disabled = Boolean(data.running) || available === 0;
            renderRows(widget, Array.isArray(data.updates) ? data.updates : []);

            const badge = root().querySelector(".cf-version-badge");
            if (badge) badge.textContent = "v22.7";
        } catch (_) {
            widget.dataset.state = "error";
            title.textContent = "Model lifecycle · service unavailable";
            subtitle.textContent = "Restart Forge after updating CivitaiFlow.";
            all.disabled = true;
            resume.disabled = true;
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
