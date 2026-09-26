"use client";

import { useState, useEffect } from "react";
import { palette } from "../../components/palette";
import { fetchWithRetry } from "../../lib/fetch-retry";
import IntegrationCard, {
  Integration,
} from "../../components/IntegrationCard";
import APIKeyDisplay from "../../components/APIKeyDisplay";
import ActivityLog, { ActivityEvent } from "../../components/ActivityLog";

interface StatusShape {
  slack: { connected: boolean; note: string };
  discord: { connected: boolean; note: string };
  telegram: { connected: boolean; note: string };
  teams: { connected: boolean; note: string };
  webhooks: { connected: boolean; count: number; note: string };
}

const integrations: Integration[] = [
  {
    name: "Slack",
    icon: "💬",
    description: "Usa AME directamente desde tus canales de Slack.",
    commands: ["/ame analyze", "/ame news"],
    installLabel: "Instalar",
    configureLabel: "Configurar",
    href: "/api/slack/install",
  },
  {
    name: "Discord",
    icon: "🎮",
    description: "Lleva el bot de AME a tus servidores de Discord.",
    commands: ["/ame"],
    installLabel: "Invitar Bot",
    configureLabel: "Configurar",
    href: "/api/discord/webhook",
  },
  {
    name: "Telegram",
    icon: "✈️",
    description: "Chat directo con AME desde Telegram.",
    commands: ["/start", "/help", "/ame"],
    installLabel: "Abrir Bot",
    configureLabel: "Configurar",
    href: "/api/telegram/webhook",
  },
  {
    name: "Microsoft Teams",
    icon: "👥",
    description: "Integra AME con los equipos de tu organización.",
    commands: ["/ame"],
    installLabel: "Agregar App",
    configureLabel: "Configurar",
    href: "/api/teams",
  },
  {
    name: "Webhooks Custom",
    icon: "🔗",
    description: "Conecta AME con cualquier servicio vía webhooks.",
    commands: ["POST /api/webhooks"],
    installLabel: "Crear Webhook",
    configureLabel: "Gestionar Webhooks",
  },
];

export default function IntegrationsPage() {
  const [status, setStatus] = useState<StatusShape | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([
    {
      time: "hace 2 min",
      integration: "Slack",
      message: "Comando /ame analyze recibido",
      status: "success",
    },
    {
      time: "hace 15 min",
      integration: "Webhooks",
      message: "Evento ame.event procesado",
      status: "info",
    },
    {
      time: "hace 1 h",
      integration: "Telegram",
      message: "Conexión de bot verificada",
      status: "success",
    },
  ]);

  const loadStatus = async () => {
    setStatusError(null);
    try {
      const res = await fetchWithRetry("/api/integrations/status");
      const data: StatusShape = await res.json();
      setStatus(data);
    } catch (e) {
      setStatusError(
        e instanceof Error ? e.message : "No se pudo cargar el estado",
      );
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const createWebhook = () => {
    const url = window.prompt("URL del endpoint para el webhook:");
    if (!url) return;

    fetch("/api/webhooks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: `wh_${Date.now()}`,
        url,
        events: ["ame.event", "integration.message"],
      }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.success) {
          setActivity((prev) => [
            {
              time: "ahora",
              integration: "Webhooks",
              message: `Webhook creado (${url})`,
              status: "success",
            },
            ...prev,
          ]);
          loadStatus();
        } else {
          window.alert("No se pudo crear el webhook: " + JSON.stringify(d));
        }
      })
      .catch((e) => window.alert("Error: " + e.message));
  };

  const list = integrations.map((i) =>
    i.name === "Webhooks Custom" ? { ...i, onClick: createWebhook } : i,
  );

  const isConnected = (name: string): boolean => {
    if (!status) return false;
    if (name === "Webhooks Custom") return status.webhooks.connected;
    return Boolean(status[name.toLowerCase() as keyof StatusShape]?.connected);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background:
          "linear-gradient(135deg, #080408 0%, #1a1a2e 100%)",
        color: palette.text,
        padding: "40px 20px",
      }}
    >
      <div
        style={{
          marginBottom: "50px",
          paddingBottom: "20px",
          borderBottom: `2px solid ${palette.border}`,
        }}
      >
        <h1 style={{ fontSize: "36px", margin: "0 0 10px 0" }}>
          🔗 Integraciones Empresariales
        </h1>
        <p style={{ opacity: 0.7, margin: 0 }}>
          Conecta AME con tus plataformas favoritas
        </p>
      </div>

      {statusError && (
        <div
          style={{
            background: "rgba(220, 20, 60, 0.12)",
            border: `1px solid ${palette.border}`,
            borderRadius: "8px",
            padding: "15px 20px",
            marginBottom: "30px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
            flexWrap: "wrap",
          }}
        >
          <span style={{ color: palette.border, fontWeight: 700 }}>
            ⚠️ No se pudo cargar el estado: {statusError}
          </span>
          <button
            onClick={loadStatus}
            style={{
              background: palette.border,
              color: palette.text,
              border: "none",
              padding: "8px 16px",
              borderRadius: "4px",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            🔄 Reintentar
          </button>
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "25px",
          marginBottom: "50px",
        }}
      >
        {list.map((integration) => (
          <IntegrationCard
            key={integration.name}
            integration={integration}
            connected={isConnected(integration.name)}
          />
        ))}
      </div>

      <APIKeyDisplay />

      <div style={{ marginBottom: "30px" }}>
        <ActivityLog events={activity} />
      </div>

      <div
        style={{
          background: palette.cardBg,
          border: `2px solid ${palette.border}`,
          borderRadius: "12px",
          padding: "25px",
        }}
      >
        <h2 style={{ margin: "0 0 15px 0" }}>📚 Documentación</h2>
        <p style={{ margin: "0 0 10px 0", opacity: 0.8 }}>
          Consulta la referencia completa de la API y el formato de
          webhooks.
        </p>
        <a
          href="/docs/webhooks"
          style={{
            color: palette.accent,
            textDecoration: "none",
            fontWeight: 700,
          }}
        >
          API Reference →
        </a>
      </div>
    </div>
  );
}
