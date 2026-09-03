"use strict";

const FORGE_BASES = [
  "http://127.0.0.1:7860",
  "http://localhost:7860",
];

let preferredBase = null;

function withTimeout(ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  return { controller, clear: () => clearTimeout(timer) };
}

async function requestForge(path, options = {}) {
  const bases = preferredBase
    ? [preferredBase, ...FORGE_BASES.filter((base) => base !== preferredBase)]
    : FORGE_BASES;

  let lastError = null;
  for (const base of bases) {
    const timeout = withTimeout(options.timeoutMs || 2200);
    try {
      const response = await fetch(`${base}${path}`, {
        method: options.method || "GET",
        headers: options.body ? { "Content-Type": "application/json" } : undefined,
        body: options.body ? JSON.stringify(options.body) : undefined,
        cache: "no-store",
        signal: timeout.controller.signal,
      });
      timeout.clear();

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        lastError = new Error(data.detail || data.label || `Forge HTTP ${response.status}`);
        continue;
      }

      preferredBase = base;
      return { ok: true, base, data };
    } catch (error) {
      timeout.clear();
      lastError = error;
    }
  }

  return {
    ok: false,
    error: lastError ? String(lastError.message || lastError) : "Forge is unavailable",
  };
}

function queryString(params) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== null && value !== undefined && value !== "") query.set(key, value);
  }
  return query.toString();
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  if (message.type === "civitaiFlowHealth") {
    requestForge("/civitaiflow/api/health")
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "civitaiFlowStatus") {
    const query = queryString({
      modelId: message.modelId,
      modelVersionId: message.modelVersionId,
    });
    requestForge(`/civitaiflow/api/status?${query}`)
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "civitaiFlowCapture") {
    requestForge("/civitaiflow/api/capture", {
      method: "POST",
      body: {
        url: message.url,
        threads: Number(message.threads) || 5,
      },
      timeoutMs: 4000,
    })
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "civitaiFlowReindex") {
    requestForge("/civitaiflow/api/reindex", { method: "POST", body: {} })
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  return false;
});
