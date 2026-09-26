(function() {
  window.addEventListener("message", (event) => {
    if (event.source !== window && event.data?.source !== "aura-extension") return;
    chrome.runtime.sendMessage({ type: "content_event", data: event.data });
  });

  function getVisibleText() {
    return document.body.innerText.slice(0, 5000);
  }

  function getSelectedText() {
    return window.getSelection()?.toString() || "";
  }

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === "get_visible_text") sendResponse({ text: getVisibleText(), url: window.location.href });
    if (msg.action === "get_selected_text") sendResponse({ text: getSelectedText(), url: window.location.href });
    if (msg.action === "highlight_text") {
      const selection = window.getSelection();
      if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        const span = document.createElement("span");
        span.style.backgroundColor = "rgba(124,77,255,0.3)";
        range.surroundContents(span);
      }
      sendResponse({ highlighted: true });
    }
  });
})();
