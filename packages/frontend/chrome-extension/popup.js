(function() {
  const statusEl = document.getElementById("status");
  const actionEl = document.getElementById("currentAction");
  const toggleBtn = document.getElementById("toggle");
  const stopBtn = document.getElementById("stop");

  function updateStatus() {
    chrome.runtime.sendMessage({ type: "get_state" }, (state) => {
      if (!state) return;
      statusEl.textContent = state.status === "connected" ? "Conectado a AURA" :
                              state.status === "connecting" ? "Conectando..." :
                              state.status === "error" ? "Error de conexión" :
                              "Desconectado";
      statusEl.className = "status " + (state.status === "connected" ? "connected" : state.status === "error" ? "error" : "disconnected");
      actionEl.textContent = state.currentAction ? `Acción: ${state.currentAction}` : "";
      toggleBtn.textContent = state.enabled ? "Desactivar AURA" : "Activar AURA";
    });
  }

  toggleBtn.addEventListener("click", () => chrome.runtime.sendMessage({ type: "toggle_enabled" }, updateStatus));
  stopBtn.addEventListener("click", () => chrome.runtime.sendMessage({ type: "run_action", action: "stop", data: {} }, updateStatus));

  setInterval(updateState, 2000);
  updateState();
})();
