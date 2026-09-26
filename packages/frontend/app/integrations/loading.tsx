import { palette } from "../../components/palette";

export default function IntegrationLoading() {
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
      <h1 style={{ fontSize: "36px", margin: "0 0 10px 0" }}>
        🔗 Integraciones Empresariales
      </h1>
      <p style={{ opacity: 0.7, margin: "0 0 30px 0" }}>
        Conecta AME con tus plataformas favoritas
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "25px",
        }}
      >
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            style={{
              background: palette.cardBg,
              border: `2px solid ${palette.border}`,
              borderRadius: "12px",
              padding: "25px",
              animation: "aura-pulse 1.5s ease-in-out infinite",
            }}
          >
            <div style={{ fontSize: "40px", marginBottom: "15px" }}>⏳</div>
            <div
              style={{
                height: "20px",
                background: "rgba(240,240,248,0.12)",
                borderRadius: "4px",
                marginBottom: "10px",
              }}
            />
            <div
              style={{
                height: "40px",
                background: "rgba(240,240,248,0.08)",
                borderRadius: "4px",
              }}
            />
          </div>
        ))}
      </div>

      <style>{`
        @keyframes aura-pulse {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
