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
                // on the host machine. For a local Forge session that works, but the
                // same-browser popup is the better authentication surface and also
                // behaves correctly when Forge is accessed remotely.
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                const popup = openCompanion(url);
                if (!popup) {
                    window.open(url, "_blank", "noopener,noreferrer");
                }
            },
            true
        );
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
    }

    if (typeof onUiLoaded === "function") onUiLoaded(bind);
    if (typeof onUiUpdate === "function") onUiUpdate(bind);
    else window.addEventListener("load", bind, { once: true });
})();
