"use client";

import { useState, useEffect } from "react";
import { palette } from "../../components/palette";
import { fetchWithRetry } from "../../lib/fetch-retry";

interface LogEntry {
  ts: string;
  level: string;
  category: string;
  message: string;
  meta: { ms?: number; status?: number } | null;
}

interface StatusShape {
  slack: { connected: boolean };
  discord: { connected: boolean };
  telegram: { connected: boolean };
  teams: { connected: boolean };
  webhooks: { connected: boolean; count: number };
}

function StatCard({ title, value, accent }: { title: string; value: string; accent?: boolean }) {
  return (
    <div
      style={{
        flex: 1,
        minWidth: "140px",
        background: palette.cardBg,
        border: `2px solid ${palette.border}`,
        borderRadius: "12px",
        padding: "18px",
        margin: "0 12px 12px 0",
      }}
    >
      <p style={{ margin: "0 0 8px 0", color: palette.accent, fontSize: "12px" }}>
        {title}
      </p>
      <p
        style={{
          margin: 0,
          fontSize: "26px",
          fontWeight: 700,
          color: accent ? palette.accent : palette.text,
        }}
      >
        {value}
      </p>
    </div>
  );
}

function BarChart({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div>
      {data.map((d) => (
        <div key={d.label} style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 4 }}>
            {d.label}
          </div>
          <div
            style={{
              background: palette.bg,
              borderRadius: 4,
              height: 18,
              width: "100%",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${(d.value / max) * 100}%`,
                background: palette.border,
                height: "100%",
                borderRadius: 4,
                transition: "width 0.4s ease",
              }}
            />
          </div>
          <div style={{ fontSize: 11, color: palette.accent, marginTop: 2 }}>
            {d.value}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<StatusShape | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setError(null);
    try {
      const [logsRes, statusRes] = await Promise.all([
        fetchWithRetry("/api/logs?limit=500"),
        fetchWithRetry("/api/integrations/status"),
      ]);
      const logsData = (await logsRes.json()).logs as LogEntry[];
      const statusData = (await statusRes.json()) as StatusShape;
      setLogs(logsData);
      setStatus(statusData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar analytics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const total = logs.length;
  const errors = logs.filter((l) => l.level === "error").length;
  const apiCalls = logs.filter((l) => l.category === "api").length;
  const apiMs = logs
    .filter((l) => l.category === "api" && l.meta?.ms)
    .map((l) => l.meta!.ms as number);
  const avgResponse = apiMs.length
    ? Math.round(apiMs.reduce((a, b) => a + b, 0) / apiMs.length)
    : 0;

  const connected = status
    ? [
        status.slack.connected,
        status.discord.connected,
        status.telegram.connected,
        status.teams.connected,
        status.webhooks.connected,
      ].filter(Boolean).length
    : 0;

  const byCategory = (() => {
    const map = new Map<string, number>();
    for (const l of logs) {
      map.set(l.category, (map.get(l.category) || 0) + 1);
    }
    return Array.from(map.entries())
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 6);
  })();

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #080408 0%, #1a1a2e 100%)",
        color: palette.text,
        padding: "40px 20px",
      }}
    >
      <div
        style={{
          marginBottom: "40px",
          paddingBottom: "20px",
          borderBottom: `2px solid ${palette.border}`,
        }}
      >
        <h1 style={{ fontSize: "36px", margin: "0 0 10px 0" }}>
          📊 Analytics
        </h1>
        <p style={{ opacity: 0.7, margin: 0 }}>
          Eventos, integraciones y rendimiento de AME
        </p>
      </div>

      {loading && (
        <p style={{ opacity: 0.7 }}>Cargando analytics…</p>
      )}

      {error && (
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
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <span style={{ color: palette.border, fontWeight: 700 }}>
            ⚠️ {error}
          </span>
          <button
            onClick={load}
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

      {!loading && !error && (
        <>
          <div style={{ display: "flex", flexWrap: "wrap", marginBottom: "30px" }}>
            <StatCard title="Eventos totales" value={String(total)} />
            <StatCard title="Integraciones OK" value={`${connected}/5`} accent />
            <StatCard title="Webhooks" value={String(status?.webhooks.count ?? 0)} />
            <StatCard title="Errores" value={String(errors)} />
            <StatCard
              title="Resp. promedio"
              value={avgResponse ? `${avgResponse}ms` : "—"}
            />
            <StatCard title="Llamadas API" value={String(apiCalls)} />
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              gap: "25px",
            }}
          >
            <div
              style={{
                background: palette.cardBg,
                border: `2px solid ${palette.border}`,
                borderRadius: "12px",
                padding: "25px",
              }}
            >
              <h2 style={{ margin: "0 0 20px 0", fontSize: "20px" }}>
                Eventos por categoría
              </h2>
              {byCategory.length ? (
                <BarChart data={byCategory} />
              ) : (
                <p style={{ opacity: 0.6, fontSize: 14 }}>
                  Sin eventos registrados aún.
                </p>
              )}
            </div>

            <div
              style={{
                background: palette.cardBg,
                border: `2px solid ${palette.border}`,
                borderRadius: "12px",
                padding: "25px",
              }}
            >
              <h2 style={{ margin: "0 0 20px 0", fontSize: "20px" }}>
                Eventos recientes
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {logs.length === 0 && (
                  <p style={{ opacity: 0.6, fontSize: 14 }}>
                    Sin eventos registrados aún.
                  </p>
                )}
                {logs
                  .slice(-12)
                  .reverse()
                  .map((log, i) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        gap: 10,
                        alignItems: "center",
                        padding: "8px 10px",
                        background: palette.bg,
                        borderRadius: 6,
                        fontSize: 12,
                      }}
                    >
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          background:
                            log.level === "error"
                              ? palette.border
                              : palette.accent,
                          flexShrink: 0,
                        }}
                      />
                      <span style={{ opacity: 0.6, minWidth: 64 }}>
                        {new Date(log.ts).toLocaleTimeString()}
                      </span>
                      <span style={{ opacity: 0.8 }}>{log.message}</span>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
