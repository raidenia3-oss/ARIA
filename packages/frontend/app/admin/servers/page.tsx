"use client";

import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";

type Server = {
  type: string;
  registered: boolean;
  active: boolean;
  url: string;
};

const card: CSSProperties = {
  background: "#1a1a2e",
  border: "2px solid #DC143C",
  borderRadius: 12,
  padding: 16,
  marginBottom: 16,
};
const btn: CSSProperties = {
  background: "linear-gradient(135deg,#DC143C,#FF1744)",
  color: "#F0F0F8",
  border: "none",
  padding: "8px 14px",
  borderRadius: 8,
  marginRight: 8,
  cursor: "pointer",
  fontWeight: "bold",
};
const inputStyle: CSSProperties = {
  width: "100%",
  padding: "10px",
  borderRadius: 8,
  border: "1px solid #DC143C",
  background: "#080408",
  color: "#F0F0F8",
  marginBottom: 8,
};

export default function ServersAdminPage() {
  const [servers, setServers] = useState<Server[]>([]);
  const [active, setActive] = useState<string>("local");
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [regType, setRegType] = useState("vercel");
  const [token, setToken] = useState("");
  const [projectId, setProjectId] = useState("");

  const push = useCallback((line: string) => setLog((p) => [line, ...p].slice(0, 40)), []);

  const fetchServers = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/servers", { cache: "no-store" });
      const data = await res.json();
      if (data.servers) {
        setServers(data.servers);
        setActive(data.active ?? "local");
      } else {
        push(`Error: ${data.error ?? "respuesta invalida"}`);
      }
    } catch (e) {
      push(`Fetch fallo: ${e instanceof Error ? e.message : String(e)}`);
    }
  }, [push]);

  useEffect(() => {
    fetchServers();
  }, [fetchServers]);

  const switchTo = async (type: string) => {
    setBusy(true);
    try {
      const res = await fetch("/api/admin/servers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "switch", server_type: type }),
      });
      const data = await res.json();
      push(data.ok ? `Activo -> ${data.active} (${data.url})` : `Switch fallo: ${data.error}`);
      await fetchServers();
    } finally {
      setBusy(false);
    }
  };

  const register = async () => {
    setBusy(true);
    try {
      const credentials: Record<string, string> = {};
      if (regType === "vercel") {
        credentials.VERCEL_TOKEN = token;
        credentials.VERCEL_PROJECT_ID = projectId;
      } else if (regType === "railway") {
        credentials.RAILWAY_TOKEN = token;
      } else if (regType === "aws") {
        credentials.AWS_ACCESS_KEY_ID = token;
        credentials.AWS_SECRET_ACCESS_KEY = projectId;
      }
      const res = await fetch("/api/admin/servers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "register", server_type: regType, credentials }),
      });
      const data = await res.json();
      push(data.ok ? `Registrado: ${regType}` : `Registro fallo: ${data.error ?? regType}`);
      setToken("");
      setProjectId("");
      await fetchServers();
    } finally {
      setBusy(false);
    }
  };

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg,#080408 0%,#1a1a2e 100%)",
        color: "#F0F0F8",
        padding: 24,
      }}
    >
      <h1 style={{ fontSize: 28, margin: "0 0 4px" }}>Server Management</h1>
      <p style={{ opacity: 0.7, marginTop: 0 }}>
        Registra, verifica y cambia entre servidores (Local / Vercel / Railway / AWS).
      </p>

      <section style={card}>
        <h3 style={{ marginTop: 0 }}>Servidor activo</h3>
        <div style={{ fontSize: 18 }}>
          <b style={{ color: "#FF1744" }}>{active}</b>
        </div>
      </section>

      <section style={card}>
        <h3 style={{ marginTop: 0 }}>Servidores</h3>
        {servers.length === 0 && <p style={{ opacity: 0.7 }}>Sin datos (backend no alcanzable?).</p>}
        {servers.map((s) => (
          <div
            key={s.type}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: "1px solid #333",
              padding: "8px 0",
            }}
          >
            <div>
              <b>{s.type}</b>{" "}
              {s.active && <span style={{ color: "#4ade80" }}>(activo)</span>}{" "}
              {!s.registered && <span style={{ color: "#f59e0b" }}>(no registrado)</span>}
              <div style={{ fontSize: 12, opacity: 0.6 }}>{s.url || "sin URL"}</div>
            </div>
            <button
              style={{ ...btn, opacity: s.registered && !s.active ? 1 : 0.5 }}
              disabled={busy || !s.registered || s.active}
              onClick={() => switchTo(s.type)}
            >
              Cambiar
            </button>
          </div>
        ))}
      </section>

      <section style={card}>
        <h3 style={{ marginTop: 0 }}>Registrar servidor</h3>
        <select value={regType} onChange={(e) => setRegType(e.target.value)} style={inputStyle}>
          <option value="vercel">Vercel</option>
          <option value="railway">Railway</option>
          <option value="aws">AWS</option>
        </select>
        <input
          type="password"
          placeholder={regType === "aws" ? "AWS_ACCESS_KEY_ID" : "API Token"}
          value={token}
          onChange={(e) => setToken(e.target.value)}
          style={inputStyle}
        />
        {(regType === "vercel" || regType === "aws") && (
          <input
            type="password"
            placeholder={regType === "vercel" ? "VERCEL_PROJECT_ID" : "AWS_SECRET_ACCESS_KEY"}
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            style={inputStyle}
          />
        )}
        <button style={btn} disabled={busy} onClick={register}>
          Registrar
        </button>
      </section>

      <section style={card}>
        <h3 style={{ marginTop: 0 }}>Log</h3>
        <pre
          style={{
            whiteSpace: "pre-wrap",
            background: "#080408",
            padding: 12,
            borderRadius: 8,
            maxHeight: 240,
            overflow: "auto",
          }}
        >
          {log.join("\n") || "Sin acciones aun."}
        </pre>
      </section>
    </main>
  );
}
