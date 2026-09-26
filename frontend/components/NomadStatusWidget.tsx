"use client";

import { useEffect, useState } from "react";
import { NomadStatusResponse } from "@/types/nomad";

const BACKEND_BASE =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") || "http://127.0.0.1:8008";

export default function NomadStatusWidget() {
  const [data, setData] = useState<NomadStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const res = await fetch(`${BACKEND_BASE}/api/nomad/status`, { cache: "no-store" });
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const json = (await res.json()) as NomadStatusResponse;
        if (!cancelled) {
          setData(json);
        }
      } catch (err) {
        if (!cancelled) {
          setData({
            status: "down",
            healthy: [],
            degraded: [],
            down: ["ollama", "qdrant"],
            total_services: 0,
            services: {},
          });
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchStatus();
    const id = setInterval(fetchStatus, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const statusColor = (status: string) => {
    if (status === "healthy") return "#00c853";
    if (status === "degraded") return "#ffab00";
    return "#ff1744";
  };

  return (
    <div
      style={{
        border: "1px solid rgba(0,240,255,0.25)",
        borderRadius: 6,
        padding: 12,
        background: "rgba(5,10,15,0.7)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <span style={{ color: "#00f0ff", fontSize: 12, letterSpacing: 2 }}>N.O.M.A.D OFFLINE</span>
        {loading ? (
          <span style={{ color: "#888", fontSize: 11 }}>Checking...</span>
        ) : (
          <span
            style={{
              color: statusColor(data?.status || "down"),
              fontSize: 11,
              fontWeight: 700,
              textShadow: `0 0 8px ${statusColor(data?.status || "down")}`,
            }}
          >
            {data?.status?.toUpperCase()}
          </span>
        )}
      </div>

      <div style={{ display: "grid", gap: 8 }}>
        {[
          { key: "ollama", label: "Ollama", port: "11434" },
          { key: "qdrant", label: "Qdrant", port: "6333" },
          { key: "kiwix", label: "Kiwix", port: "8080" },
          { key: "protomaps", label: "ProtoMaps", port: "8100" },
        ].map((item) => {
          const service = data?.services?.[item.key];
          const status = service?.status || "down";
          return (
            <div
              key={item.key}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                fontSize: 11,
                color: "#cfefff",
                background: "rgba(0,240,255,0.04)",
                border: `1px solid rgba(0,240,255,0.12)`,
                borderRadius: 4,
                padding: "6px 8px",
              }}
            >
              <span>{item.label}</span>
              <span style={{ color: "#6b7b8d", fontFamily: "monospace" }}>:{item.port}</span>
              <span
                style={{
                  color: statusColor(status),
                  fontWeight: 700,
                  textShadow: `0 0 6px ${statusColor(status)}`,
                }}
              >
                {status.toUpperCase()}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
