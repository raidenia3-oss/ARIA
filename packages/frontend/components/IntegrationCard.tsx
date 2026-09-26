"use client";

import { palette } from "./palette";
import StatusBadge from "./StatusBadge";
import InstallButton from "./InstallButton";

export interface Integration {
  name: string;
  icon: string;
  description: string;
  commands: string[];
  installLabel: string;
  configureLabel: string;
  href?: string;
  onClick?: () => void;
}

interface IntegrationCardProps {
  integration: Integration;
  connected: boolean;
}

export default function IntegrationCard({
  integration,
  connected,
}: IntegrationCardProps) {
  const base: React.CSSProperties = {
    background: palette.cardBg,
    border: `2px solid ${palette.border}`,
    borderRadius: "12px",
    padding: "25px",
    transition: "all 0.3s ease",
  };

  const hover: React.CSSProperties = {
    borderColor: palette.accent,
    boxShadow: "0 0 20px rgba(255, 215, 0, 0.3)",
    transform: "translateY(-4px)",
  };

  return (
    <div
      style={base}
      onMouseEnter={(e) => Object.assign(e.currentTarget.style, hover)}
      onMouseLeave={(e) => Object.assign(e.currentTarget.style, base)}
    >
      <div style={{ fontSize: "40px", marginBottom: "15px" }}>
        {integration.icon}
      </div>

      <h3 style={{ margin: "0 0 10px 0", fontSize: "20px" }}>
        {integration.name}
      </h3>

      <p
        style={{
          margin: "0 0 15px 0",
          opacity: 0.8,
          fontSize: "14px",
          minHeight: "38px",
        }}
      >
        {integration.description}
      </p>

      <div style={{ marginBottom: "15px" }}>
        <StatusBadge connected={connected} />
      </div>

      <div
        style={{
          marginBottom: "20px",
          padding: "12px",
          background: palette.bg,
          borderRadius: "4px",
          fontSize: "12px",
        }}
      >
        <p style={{ margin: "0 0 8px 0", opacity: 0.7 }}>Comandos:</p>
        {integration.commands.map((cmd) => (
          <div key={cmd} style={{ margin: "4px 0" }}>
            <code style={{ color: palette.accent }}>{cmd}</code>
          </div>
        ))}
      </div>

      <InstallButton
        connected={connected}
        href={integration.href}
        installLabel={integration.installLabel}
        configureLabel={integration.configureLabel}
        onClick={integration.onClick}
      />
    </div>
  );
}
