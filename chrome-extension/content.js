/* AURA Bridge — content script injected into web pages */

(function () {
  if (window.__auraBridgeInjected) return;
  window.__auraBridgeInjected = true;

  window.__auraBridge = {
    injectScript(code) {
      try {
        const script = document.createElement("script");
        script.src = code;
        document.head.appendChild(script);
        return { success: true };
      } catch (e) {
        return { success: false, error: String(e) };
      }
    },
    readDOM(selector) {
      try {
        const el = document.querySelector(selector);
        return el ? el.outerHTML : null;
      } catch (e) {
        return null;
      }
    },
    modifyDOM(selector, html) {
      try {
        const el = document.querySelector(selector);
        if (!el) return { success: false };
        el.innerHTML = html;
        return { success: true };
      } catch (e) {
        return { success: false, error: String(e) };
      }
    },
    getCookies() {
      try {
        return document.cookie;
      } catch (e) {
        return "";
      }
    }
  };
})();
