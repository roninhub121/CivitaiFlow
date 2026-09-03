(() => {
  "use strict";

  const MODEL_PATH_RE = /^\/models\/(\d+)(?:[\/?#]|$)/;
  const ENHANCED_ATTR = "data-civitai-flow-enhanced";
  const PAGE_BUTTON_ID = "civitai-flow-page-send";
  const STYLE_ID = "civitai-flow-browser-bridge-style";
  const STATUS_TTL_MS = 2600;
  const statusCache = new Map();

  function targetFromUrl(value) {
    try {
      const url = new URL(value, window.location.href);
      if (url.hostname !== "civitai.com" && !url.hostname.endsWith(".civitai.com")) return null;

      const match = url.pathname.match(MODEL_PATH_RE);
      if (!match) return null;

      const canonical = new URL(`https://civitai.com/models/${match[1]}`);
      const versionId = url.searchParams.get("modelVersionId");
      if (versionId) canonical.searchParams.set("modelVersionId", versionId);

      return {
        url: canonical.toString(),
        modelId: match[1],
        modelVersionId: versionId || null,
        key: `${match[1]}:${versionId || "latest"}`,
      };
    } catch (_) {
      return null;
    }
  }

  async function writeClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      try {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.setAttribute("readonly", "");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        textarea.style.pointerEvents = "none";
        document.documentElement.appendChild(textarea);
        textarea.select();
        const ok = document.execCommand("copy");
        textarea.remove();
        return ok;
      } catch (_) {
        return false;
      }
    }
  }

  function bridgeMessage(message) {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage(message, (response) => {
          if (chrome.runtime.lastError) {
            resolve({ ok: false, error: chrome.runtime.lastError.message });
            return;
          }
          resolve(response || { ok: false, error: "No response from CivitaiFlow Browser Bridge" });
        });
      } catch (error) {
        resolve({ ok: false, error: String(error) });
      }
    });
  }

  function sendIcon() {
    return `
      <svg viewBox="0 0 20 20" aria-hidden="true">
        <path d="M10 3.2v9.1m0 0 3.2-3.2M10 12.3 6.8 9.1" />
        <path d="M4.2 12.7v2.1A1.2 1.2 0 0 0 5.4 16h9.2a1.2 1.2 0 0 0 1.2-1.2v-2.1" />
      </svg>`;
  }

  function checkIcon() {
    return `
      <svg viewBox="0 0 20 20" aria-hidden="true">
        <path d="m5.2 10.3 3 3 6.6-6.6" />
      </svg>`;
  }

  function updateIcon() {
    return `
      <svg viewBox="0 0 20 20" aria-hidden="true">
        <path d="M10 16.5V7.2m0 0L6.8 10.4M10 7.2l3.2 3.2" />
        <path d="M4 5.2h12" />
      </svg>`;
  }

  function spinnerIcon() {
    return `
      <svg class="civitai-flow-spin" viewBox="0 0 20 20" aria-hidden="true">
        <path d="M16 10a6 6 0 1 1-1.8-4.3" />
      </svg>`;
  }

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .civitai-flow-card-root {
        position: relative !important;
      }

      .civitai-flow-send {
        appearance: none !important;
        position: absolute !important;
        top: 10px !important;
        left: 50% !important;
        transform: translateX(-50%) translateY(-2px) !important;
        z-index: 2147483000 !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 6px !important;
        height: 32px !important;
        padding: 0 11px !important;
        border: 1px solid rgba(255,255,255,.18) !important;
        border-radius: 9px !important;
        background: rgba(10, 13, 20, .86) !important;
        color: #f8fafc !important;
        box-shadow: 0 8px 22px rgba(0,0,0,.28) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        font: 650 12px/1 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
        letter-spacing: -.01em !important;
        cursor: pointer !important;
        opacity: 0 !important;
        transition: opacity .14s ease, transform .14s ease, background .14s ease, border-color .14s ease !important;
        white-space: nowrap !important;
      }

      .civitai-flow-card-root:hover > .civitai-flow-send,
      .civitai-flow-send:focus-visible,
      .civitai-flow-send[data-state="installed"],
      .civitai-flow-send[data-state="update"],
      .civitai-flow-send[data-state="downloading"],
      .civitai-flow-send[data-state="queued"],
      .civitai-flow-send[data-state="verifying"],
      .civitai-flow-send[data-state="indexing"],
      .civitai-flow-send[data-state="error"] {
        opacity: 1 !important;
        transform: translateX(-50%) translateY(0) !important;
      }

      .civitai-flow-send:hover {
        background: rgba(249, 115, 22, .96) !important;
        border-color: rgba(255,255,255,.28) !important;
      }

      .civitai-flow-send[data-state="installed"] {
        background: rgba(5, 150, 105, .94) !important;
      }

      .civitai-flow-send[data-state="update"] {
        background: rgba(217, 119, 6, .95) !important;
      }

      .civitai-flow-send[data-state="downloading"],
      .civitai-flow-send[data-state="queued"],
      .civitai-flow-send[data-state="verifying"] {
        background: rgba(37, 99, 235, .94) !important;
      }

      .civitai-flow-send[data-state="indexing"] {
        background: rgba(71, 85, 105, .94) !important;
      }

      .civitai-flow-send[data-state="error"] {
        background: rgba(190, 24, 93, .94) !important;
      }

      .civitai-flow-send svg,
      #${PAGE_BUTTON_ID} svg {
        width: 15px !important;
        height: 15px !important;
        fill: none !important;
        stroke: currentColor !important;
        stroke-width: 1.8 !important;
        stroke-linecap: round !important;
        stroke-linejoin: round !important;
        flex: 0 0 auto !important;
      }

      .civitai-flow-spin {
        animation: civitai-flow-spin .9s linear infinite !important;
      }

      @keyframes civitai-flow-spin {
        to { transform: rotate(360deg); }
      }

      #${PAGE_BUTTON_ID} {
        appearance: none !important;
        position: fixed !important;
        right: 22px !important;
        bottom: 22px !important;
        z-index: 2147483000 !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 8px !important;
        min-height: 42px !important;
        padding: 0 15px !important;
        border: 1px solid rgba(255,255,255,.18) !important;
        border-radius: 11px !important;
        background: rgba(249, 115, 22, .94) !important;
        color: #fff !important;
        box-shadow: 0 12px 34px rgba(0,0,0,.34) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        font: 700 13px/1 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
        cursor: pointer !important;
      }

      #${PAGE_BUTTON_ID}[data-state="installed"] { background: rgb(5, 150, 105) !important; }
      #${PAGE_BUTTON_ID}[data-state="update"] { background: rgb(217, 119, 6) !important; }
      #${PAGE_BUTTON_ID}[data-state="downloading"],
      #${PAGE_BUTTON_ID}[data-state="queued"],
      #${PAGE_BUTTON_ID}[data-state="verifying"] { background: rgb(37, 99, 235) !important; }
      #${PAGE_BUTTON_ID}[data-state="indexing"] { background: rgb(71, 85, 105) !important; }
      #${PAGE_BUTTON_ID}[data-state="error"] { background: rgb(190, 24, 93) !important; }

      @media (hover: none) {
        .civitai-flow-send {
          opacity: 1 !important;
          transform: translateX(-50%) translateY(0) !important;
        }
      }
    `;
    document.documentElement.appendChild(style);
  }

  function findCardRoot(anchor) {
    let node = anchor;

    for (let depth = 0; depth < 7 && node; depth += 1, node = node.parentElement) {
      if (!(node instanceof HTMLElement)) continue;

      const rect = node.getBoundingClientRect();
      const hasImage = Boolean(node.querySelector("img, video"));
      const modelLinks = node.querySelectorAll('a[href*="/models/"]').length;

      if (
        hasImage &&
        rect.width >= 150 &&
        rect.height >= 150 &&
        rect.width <= 760 &&
        rect.height <= 980 &&
        modelLinks <= 10
      ) {
        return node;
      }
    }

    return anchor.parentElement instanceof HTMLElement ? anchor.parentElement : null;
  }

  function statePresentation(state, data = {}) {
    if (state === "installed") return { icon: checkIcon(), label: "Installed" };
    if (state === "update") return { icon: updateIcon(), label: "Update available" };
    if (state === "queued") return { icon: spinnerIcon(), label: "Queued" };
    if (state === "verifying") return { icon: spinnerIcon(), label: "Verifying" };
    if (state === "indexing") return { icon: spinnerIcon(), label: "Indexing library" };
    if (state === "downloading") {
      const progress = Number(data.progress);
      return {
        icon: spinnerIcon(),
        label: Number.isFinite(progress) ? `Downloading ${Math.round(progress)}%` : "Downloading",
      };
    }
    if (state === "error") return { icon: sendIcon(), label: "Retry in Forge" };
    return { icon: sendIcon(), label: "Send to Forge" };
  }

  function setButtonState(button, state, data = {}) {
    const presentation = statePresentation(state, data);
    button.dataset.state = state || "available";
    button.innerHTML = `${presentation.icon}<span>${presentation.label}</span>`;

    if (data.path) button.title = `Installed locally: ${data.path}`;
    else if (state === "update") button.title = "A different local version is installed. Click to send the current/latest version to Forge.";
    else if (state === "indexing") button.title = "CivitaiFlow is building the SHA-256 library index. Downloads are held until the index is ready.";
    else button.title = "Send this model directly to the local CivitaiFlow service. Clipboard/Sniper is used only as a fallback.";
  }

  function buttonTarget(button) {
    return targetFromUrl(button.dataset.modelUrl || window.location.href);
  }

  async function getStatus(target, force = false) {
    if (!target) return null;
    const cached = statusCache.get(target.key);
    const now = Date.now();
    if (!force && cached && now - cached.time < STATUS_TTL_MS) return cached.data;

    const response = await bridgeMessage({
      type: "civitaiFlowStatus",
      modelId: target.modelId,
      modelVersionId: target.modelVersionId,
    });

    if (!response.ok || !response.data) return null;
    statusCache.set(target.key, { time: now, data: response.data });
    return response.data;
  }

  async function refreshStatus(button, force = false) {
    if (!button || !button.isConnected) return;
    const target = buttonTarget(button);
    if (!target) return;

    const data = await getStatus(target, force);
    if (!data || !button.isConnected) return;
    setButtonState(button, data.state || "available", data);
  }

  async function fallbackToSniper(button, target) {
    const copied = await writeClipboard(target.url);
    if (!copied) {
      setButtonState(button, "error", { error: "Clipboard write failed" });
      return;
    }

    button.dataset.state = "queued";
    button.innerHTML = `${checkIcon()}<span>Sent via Sniper</span>`;
    window.setTimeout(() => void refreshStatus(button, true), 1400);
  }

  async function capture(button) {
    const target = buttonTarget(button);
    if (!target) return;

    const existingStatus = await getStatus(target, true);
    if (existingStatus && existingStatus.state === "installed") {
      setButtonState(button, "installed", existingStatus);
      return;
    }

    setButtonState(button, "queued", { label: "Sending" });
    const response = await bridgeMessage({
      type: "civitaiFlowCapture",
      url: target.url,
    });

    if (!response.ok || !response.data) {
      await fallbackToSniper(button, target);
      return;
    }

    const data = response.data;
    statusCache.set(target.key, { time: Date.now(), data });
    setButtonState(button, data.state || "queued", data);

    if (["queued", "downloading", "verifying"].includes(data.state)) {
      window.setTimeout(() => void refreshStatus(button, true), 650);
    }
  }

  function configureButton(button, target) {
    button.dataset.modelUrl = target.url;
    button.dataset.modelId = target.modelId;
    if (target.modelVersionId) button.dataset.modelVersionId = target.modelVersionId;
    else delete button.dataset.modelVersionId;
    setButtonState(button, "available");
  }

  function enhanceCards() {
    const links = document.querySelectorAll('a[href*="/models/"]');
    const seenRoots = new Set();

    for (const anchor of links) {
      if (!(anchor instanceof HTMLAnchorElement)) continue;
      const target = targetFromUrl(anchor.href);
      if (!target) continue;

      const root = findCardRoot(anchor);
      if (!root || seenRoots.has(root)) continue;
      seenRoots.add(root);

      const rect = root.getBoundingClientRect();
      if (rect.width < 150 || rect.height < 150) continue;

      let button = root.querySelector(":scope > .civitai-flow-send");
      if (!button) {
        root.setAttribute(ENHANCED_ATTR, "1");
        root.classList.add("civitai-flow-card-root");

        button = document.createElement("button");
        button.type = "button";
        button.className = "civitai-flow-send";
        button.addEventListener(
          "click",
          (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
            void capture(button);
          },
          true
        );
        root.appendChild(button);
      }

      if (button.dataset.modelUrl !== target.url) configureButton(button, target);
      void refreshStatus(button);
    }
  }

  function enhanceModelPage() {
    const target = targetFromUrl(window.location.href);
    const existing = document.getElementById(PAGE_BUTTON_ID);

    if (!target) {
      if (existing) existing.remove();
      return;
    }

    let button = existing;
    if (!button) {
      button = document.createElement("button");
      button.id = PAGE_BUTTON_ID;
      button.type = "button";
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        void capture(button);
      });
      document.documentElement.appendChild(button);
    }

    if (button.dataset.modelUrl !== target.url) configureButton(button, target);
    void refreshStatus(button);
  }

  function isVisible(button) {
    const rect = button.getBoundingClientRect();
    return rect.bottom >= 0 && rect.top <= window.innerHeight && rect.right >= 0 && rect.left <= window.innerWidth;
  }

  function refreshVisibleStatuses() {
    if (document.hidden) return;
    const buttons = document.querySelectorAll(`.civitai-flow-send, #${PAGE_BUTTON_ID}`);
    for (const button of buttons) {
      if (isVisible(button)) void refreshStatus(button);
    }
  }

  let scheduled = false;
  function scheduleScan() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      ensureStyles();
      enhanceCards();
      enhanceModelPage();
    });
  }

  const observer = new MutationObserver(scheduleScan);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  window.addEventListener("popstate", scheduleScan);
  window.addEventListener("hashchange", scheduleScan);
  window.addEventListener("focus", () => {
    statusCache.clear();
    scheduleScan();
    refreshVisibleStatuses();
  });

  window.setInterval(refreshVisibleStatuses, 2500);
  scheduleScan();
})();
