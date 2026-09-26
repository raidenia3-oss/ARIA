const fetch = require("node-fetch");

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3000";

async function checkIntegration(name, path) {
  try {
    const res = await fetch(`${BASE_URL}${path}`);
    const status = res.status;
    const ok = res.ok;
    console.log(`${ok ? '✅' : '❌'} ${name} (${path}) - Status: ${status}`);
    return ok;
  } catch (error) {
    console.log(`❌ ${name} (${path}) - Error: ${error.message}`);
    return false;
  }
}

async function monitorIntegrations() {
  console.log(`\n--- Iniciando monitoreo de integraciones (${new Date().toLocaleString()}) ---`);
  const results = [
    await checkIntegration("Health Check", "/api/health"),
    await checkIntegration("AME Core", "/api/ame-core"),
    await checkIntegration("Slack Events", "/api/slack/events"),
    await checkIntegration("Discord Webhook", "/api/discord/webhook"),
    await checkIntegration("Telegram Webhook", "/api/telegram/webhook"),
    await checkIntegration("Teams", "/api/teams"),
  ];

  const allOk = results.every(r => r);
  if (!allOk) {
    console.log("🚨 ¡Alerta! Una o más integraciones están fallando.");
    // Aquí se podría añadir lógica para enviar notificaciones (email, SMS, Slack, etc.)
  }
  console.log("--- Monitoreo completado ---\n");
}

// Ejecutar monitoreo cada 5 minutos
setInterval(monitorIntegrations, 5 * 60 * 1000);

monitorIntegrations(); // Ejecutar inmediatamente al inicio
