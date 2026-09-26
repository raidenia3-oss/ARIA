// AURA - Content Script (inyecta avatar en páginas)
const API_BASE = "https://aura-web-chi-seven.vercel.app/api";

// Crear contenedor del avatar
const container = document.createElement("div");
container.id = "aura-avatar-container";
container.style.cssText =
  "position: fixed; bottom: 20px; right: 20px; width: 120px; height: 120px; z-index: 999999; cursor: grab;";
document.body.appendChild(container);

// Inyectar Three.js
const script = document.createElement("script");
script.src = "https://cdn.jsdelivr.net/npm/three@0.158.0/build/three.min.js";
script.onload = () => {
  console.log("AURA: Three.js loaded");
};
document.head.appendChild(script);

// Renderizar avatar simple (círculo con color)
function renderAvatar(emotion) {
  const colors = {
    idle: "#DC143C",
    happy: "#FFD700",
    thinking: "#4169E1",
    alert: "#FF4500",
  };
  const color = colors[emotion] || colors.idle;
  container.innerHTML = `<div style="width: 100%; height: 100%; background: ${color}; border-radius: 50%; box-shadow: 0 0 20px ${color}; animation: pulse 2s infinite;"></div>`;
}

renderAvatar("idle");

// Click para cambiar emoción
container.addEventListener("click", () => {
  const emotions = ["idle", "happy", "thinking", "alert"];
  const current = emotions[0];
  const next = emotions[(emotions.indexOf(current) + 1) % emotions.length];
  renderAvatar(next);
  chrome.runtime.sendMessage({ type: "UPDATE_EMOTION", emotion: next });
});

// Arrastrar avatar
let isDragging = false;
container.addEventListener("mousedown", () => (isDragging = true));
document.addEventListener("mouseup", () => (isDragging = false));
document.addEventListener("mousemove", (e) => {
  if (!isDragging) return;
  container.style.left = e.clientX - 60 + "px";
  container.style.top = e.clientY - 60 + "px";
  container.style.right = "auto";
});
