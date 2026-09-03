(() => {
  "use strict";

  const MODEL_PATH_RE = /^\/models\/(\d+)(?:[\/?#]|$)/;
  const ENHANCED_ATTR = "data-civitai-flow-enhanced";
  const PAGE_BUTTON_ID = "civitai-flow-page-send";
  const STYLE_ID = "civitai-flow-browser-bridge-style";

  function canonicalModelUrl(value) {
    try {
      const url = new URL(value, window.location.href);
      if (url.hostname !== "civitai.com" && !url.hostname.endsWith(".civitai.com")) return null;

      const match = url.pathname.match(MODEL_PATH_RE);
      if (!match) return null;

      const canonical = new URL(`https://civitai.com/models/${match[1]}`);
      const versionId = url.searchParams.get("modelVersionId");
      if (versionId) canonical.searchParams.set("modelVersionId", versionId);
      return canonical.toString();
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
        background: rgba(10, 13, 20, .84) !important;
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
      .civitai-flow-send:focus-visible {
        opacity: 1 !important;
        transform: translateX(-50%) translateY(0) !important;
      }

      .civitai-flow-send:hover {
        background: rgba(249, 115, 22, .94) !important;
        border-color: rgba(255,255,255,.28) !important;
      }

      .civitai-flow-send[data-state="sent"] {
        opacity: 1 !important;
        background: rgba(5, 150, 105, .94) !important;
      }

      .civitai-flow-send[data-state="error"] {
        opacity: 1 !important;
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

      #${PAGE_BUTTON_ID}:hover {
        background: rgb(234, 88, 12) !important;
      }

      #${PAGE_BUTTON_ID}[data-state="sent"] {
        background: rgb(5, 150, 105) !important;
      }

      #${PAGE_BUTTON_ID}[data-state="error"] {
        background: rgb(190, 24, 93) !important;
      }

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

  function setButtonState(button, state, label) {
    button.dataset.state = state;
    button.innerHTML = `${state === "sent" ? checkIcon() : sendIcon()}<span>${label}</span>`;
  }

  async function capture(button, url) {
    setButtonState(button, "working", "Sending…");
    const copied = await writeClipboard(url);

    if (copied) {
      setButtonState(button, "sent", "Sent to Forge");
      window.setTimeout(() => {
        if (button.isConnected) setButtonState(button, "idle", "Send to Forge");
      }, 1400);
    } else {
      setButtonState(button, "error", "Copy failed");
      window.setTimeout(() => {
        if (button.isConnected) setButtonState(button, "idle", "Send to Forge");
      }, 1800);
    }
  }

  function enhanceCards() {
    const links = document.querySelectorAll('a[href*="/models/"]');
    const seenRoots = new Set();

    for (const anchor of links) {
      if (!(anchor instanceof HTMLAnchorElement)) continue;
      const url = canonicalModelUrl(anchor.href);
      if (!url) continue;

      const root = findCardRoot(anchor);
      if (!root || seenRoots.has(root) || root.hasAttribute(ENHANCED_ATTR)) continue;
      seenRoots.add(root);

      const rect = root.getBoundingClientRect();
      if (rect.width < 150 || rect.height < 150) continue;

      root.setAttribute(ENHANCED_ATTR, "1");
      root.classList.add("civitai-flow-card-root");

      const button = document.createElement("button");
      button.type = "button";
      button.className = "civitai-flow-send";
      button.title = "Send this model to CivitaiFlow. This copies the model URL so Sniper capture can queue it immediately.";
      setButtonState(button, "idle", "Send to Forge");

      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        void capture(button, url);
      }, true);

      root.appendChild(button);
    }
  }

  function enhanceModelPage() {
    const url = canonicalModelUrl(window.location.href);
    const existing = document.getElementById(PAGE_BUTTON_ID);

    if (!url) {
      if (existing) existing.remove();
      return;
    }

    if (existing) {
      existing.dataset.modelUrl = url;
      return;
    }

    const button = document.createElement("button");
    button.id = PAGE_BUTTON_ID;
    button.type = "button";
    button.dataset.modelUrl = url;
    button.title = "Send the current Civitai model to CivitaiFlow";
    setButtonState(button, "idle", "Send to Forge");
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      void capture(button, button.dataset.modelUrl || url);
    });
    document.documentElement.appendChild(button);
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

  scheduleScan();
})();
