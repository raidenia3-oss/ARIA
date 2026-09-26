"use client";
import { useState, useEffect } from "react";

export default function EvolutionDashboard() {
  const [, setMetrics] = useState([]);

  useEffect(() => {
    const loadMetrics = async () => {
      try {
        const data = await fetch("/api/ame/evolution/metrics");
        const metrics = await data.json();
        setMetrics(metrics);
      } catch {
        console.log("Métricas de evolución no disponibles");
      }
    };

    loadMetrics();
    const interval = setInterval(loadMetrics, 3600000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      style={{
        background: "#080408",
        color: "#F0F0F8",
        padding: "20px",
        minHeight: "100vh",
      }}
    >
      <h1>📈 Evolución de AME</h1>
      <p style={{ opacity: 0.7 }}>
        Monitoreo del crecimiento automático del sistema.
      </p>

      <div
        style={{
          display: "grid",
          gap: "15px",
          marginTop: "20px",
        }}
      >
        <div
          style={{
            background: "#1a1a2e",
            border: "2px solid #DC143C",
            borderRadius: "8px",
            padding: "20px",
          }}
        >
          <h3 style={{ margin: "0 0 10px 0" }}>🧠 Autoaprendizaje</h3>
          <p style={{ margin: "0", opacity: 0.8 }}>
            Patrones analizados y mejoras aplicadas.
          </p>
        </div>

        <div
          style={{
            background: "#1a1a2e",
            border: "2px solid #DC143C",
            borderRadius: "8px",
            padding: "20px",
          }}
        >
          <h3 style={{ margin: "0 0 10px 0" }}>🌟 Habilidades</h3>
          <p style={{ margin: "0", opacity: 0.8 }}>
            Skills nuevas descubiertas automáticamente.
          </p>
        </div>

        <div
          style={{
            background: "#1a1a2e",
            border: "2px solid #DC143C",
            borderRadius: "8px",
            padding: "20px",
          }}
        >
          <h3 style={{ margin: "0 0 10px 0" }}>⚡ Optimización</h3>
          <p style={{ margin: "0", opacity: 0.8 }}>
            Recursos optimizados sin intervención.
          </p>
        </div>

        <div
          style={{
            background: "#1a1a2e",
            border: "2px solid #DC143C",
            borderRadius: "8px",
            padding: "20px",
          }}
        >
          <h3 style={{ margin: "0 0 10px 0" }}>📊 Métricas</h3>
          <p style={{ margin: "0", opacity: 0.8 }}>
            Seguimiento de evolución en tiempo real.
          </p>
        </div>
      </div>
    </div>
  );
}
