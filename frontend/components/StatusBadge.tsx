import { palette } from "./palette";

export default function StatusBadge({ connected }: { connected: boolean }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "6px 12px",
        borderRadius: "20px",
        fontSize: "12px",
        fontWeight: 700,
        background: connected
          ? "rgba(0, 200, 83, 0.12)"
          : "rgba(220, 20, 60, 0.12)",
        color: connected ? palette.green : palette.border,
        border: `1px solid ${
          connected
            ? "rgba(0, 200, 83, 0.4)"
            : "rgba(220, 20, 60, 0.4)"
        }`,
      }}
    >
      <span
        style={{
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          background: connected ? palette.green : palette.border,
          boxShadow: `0 0 8px ${
            connected ? palette.green : palette.border
          }`,
        }}
      />
      {connected ? "Conectado" : "Desconectado"}
    </span>
  );
}
