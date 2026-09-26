"use client";

import { palette } from "../../components/palette";

export default function IntegrationError({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div
      style={{
        minHeight: "100vh",
        background:
          "linear-gradient(135deg, #080408 0%, #1a1a2e 100%)",
        color: palette.text,
        padding: "40px 20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          background: palette.cardBg,
          border: `2px solid ${palette.border}`,
          borderRadius: "8px",
          padding: "30px",
          textAlign: "center",
          maxWidth: "420px",
        }}
      >
        <h2 style={{ margin: "0 0 15px 0" }}>Error en Integraciones</h2>
        <p style={{ opacity: 0.8, margin: "0 0 20px 0" }}>
          {error.message || "Ocurrio un error inesperado."}
        </p>
        <button
          onClick={reset}
          style={{
            background: palette.border,
            color: palette.text,
            padding: "10px 20px",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
            fontWeight: 700,
          }}
        >
          Reintentar
        </button>
      </div>
    </div>
  );
}
