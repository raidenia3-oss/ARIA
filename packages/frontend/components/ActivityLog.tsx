"use client";

import { palette } from "./palette";

export interface ActivityEvent {
  time: string;
  integration: string;
  message: string;
  status?: "success" | "info" | "error";
}

const statusColor: Record<string, string> = {
  success: palette.green,
  info: palette.accent,
  error: palette.border,
};

export default function ActivityLog({ events }: { events: ActivityEvent[] }) {
  return (
    <div
      style={{
        background: palette.cardBg,
        border: `2px solid ${palette.border}`,
        borderRadius: "12px",
        padding: "25px",
      }}
    >
      <h2 style={{ margin: "0 0 20px 0" }}>📈 Actividad</h2>

      {events.length === 0 ? (
        <p style={{ opacity: 0.6, fontSize: "14px" }}>
          Sin eventos recientes. Conecta una integración para empezar.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {events.map((event, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                padding: "10px 12px",
                background: palette.bg,
                borderRadius: "6px",
                fontSize: "13px",
              }}
            >
              <span
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  flexShrink: 0,
                  background:
                    statusColor[event.status || "info"] ||
                    palette.accent,
                }}
              />
              <span style={{ opacity: 0.6, minWidth: "70px" }}>
                {event.time}
              </span>
              <span style={{ fontWeight: 700, color: palette.accent }}>
                {event.integration}
              </span>
              <span style={{ flex: 1, opacity: 0.85 }}>
                {event.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
