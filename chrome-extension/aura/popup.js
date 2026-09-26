// AURA - Popup Script
document.addEventListener("DOMContentLoaded", () => {
  const avatar = document.getElementById("avatar");
  const label = document.getElementById("emotion-label");
  const syncBtn = document.getElementById("sync-btn");
  const buttons = document.querySelectorAll(".btn[data-emotion]");

  const colors = {
    idle: "#DC143C",
    happy: "#FFD700",
    thinking: "#4169E1",
    alert: "#FF4500",
  };

  function setEmotion(emotion) {
    const color = colors[emotion] || colors.idle;
    avatar.style.background = color;
    avatar.style.boxShadow = `0 0 20px ${color}`;
    label.textContent = emotion;
    chrome.runtime.sendMessage({ type: "UPDATE_EMOTION", emotion });
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => setEmotion(btn.dataset.emotion));
  });

  syncBtn.addEventListener("click", async () => {
    syncBtn.textContent = "⏳ Sincronizando...";
    try {
      const res = await fetch("https://aura-web-chi-seven.vercel.app/api/sync");
      const data = await res.json();
      syncBtn.textContent = `✅ ${new Date(data.timestamp).toLocaleTimeString()}`;
    } catch {
      syncBtn.textContent = "❌ Error";
    }
    setTimeout(() => (syncBtn.textContent = "🔄 Sincronizar"), 2000);
  });

  setEmotion("idle");
});
