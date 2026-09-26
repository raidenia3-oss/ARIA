"use client";
import { useEffect, useRef, useState } from "react";
import { ParticleSystem3D } from "@/lib/particle-system";
import { AmestatusSyncManager } from "@/lib/ame-sync";
import type { Amestatus } from "@/lib/ame-state-machine";

type CoreState = Amestatus;

const STATE_META: Record<CoreState, { label: string; color: string; mode: "idle" | "aura" | "vortex" | "stream" | "beam" | "implosion" | "domain_expansion" }> = {
  independent: { label: "Independiente", color: "#00C855", mode: "idle" },
  discovering: { label: "Descubriendo AURA", color: "#FFD700", mode: "beam" },
  pairing: { label: "Emparejando", color: "#FFD700", mode: "beam" },
  connecting: { label: "Conectando", color: "#FFD700", mode: "vortex" },
  connected: { label: "Conectado", color: "#00C853", mode: "aura" },
  delegating: { label: "Delegando", color: "#00e5ff", mode: "stream" },
  syncing: { label: "Sincronizando", color: "#7c4dff", mode: "stream" },
  disconnected: { label: "Desconectado", color: "#DC143C", mode: "implosion" },
  reconnecting: { label: "Reconectando", color: "#00e5ff", mode: "vortex" },
  offline_pending: { label: "Offline con pendientes", color: "#FFD700", mode: "idle" },
  revoked: { label: "Revocado", color: "#DC143C", mode: "implosion" },
  auth_failed: { label: "Auth fallida", color: "#DC143C", mode: "implosion" },
};

type Telemetry = {
  cpu: number;
  memory: number;
  disk: number;
  network: { bytes_sent?: number; bytes_recv?: number };
  timestamp: number;
};

const INITIAL_LOGS = [{ ts: new Date().toLocaleTimeString("es-ES"), msg: "Núcleo iniciado" }];

export default function AuraCorePage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<ParticleSystem3D | null>(null);
  const [state, setState] =   useState<CoreState>("independent");
  const [time, setTime] = useState("");
  const [logs, setLogs] = useState(INITIAL_LOGS);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [diagnosing, setDiagnosing] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [tasks, setTasks] = useState<Array<Record<string, unknown>>>([]);
  const [procedures, setProcedures] = useState<Array<Record<string, unknown>>>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setReducedMotion(window.matchMedia("(prefers-reduced-motion: reduce)").matches);

    const syncManager = AmestatusSyncManager.getInstance();
    syncManager.init().catch((error: unknown) => {
      console.error("No se pudo iniciar la sincronización:", error);
      addLog("Error al iniciar sincronización");
    });

    const unsubscribe = syncManager.subscribe((s) => {
      setState(s.ameStatus);
      addLog(`Estado: ${STATE_META[s.ameStatus]?.label || s.ameStatus}`);
    });

    return () => {
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    let active = true;
    const readTelemetry = async () => {
      try {
        const response = await fetch("/api/system/telemetry", { cache: "no-store" });
        if (!response.ok) throw new Error(`Telemetry ${response.status}`);
        const data = (await response.json()) as Telemetry;
        if (active) setTelemetry(data);
      } catch (error: unknown) {
        if (active) console.warn("Telemetría no disponible:", error);
      }
    };
    void readTelemetry();
    const id = setInterval(readTelemetry, 10000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const load = async () => {
    setLoadingTasks(true);
    try {
      const [tasksRes, procRes] = await Promise.all([
        fetch("/api/tasks", { cache: "no-store" }),
        fetch("/api/automation/procedures", { cache: "no-store" }),
      ]);
      const tasksData = tasksRes.ok ? await tasksRes.json() : { tasks: [] };
      const procData = procRes.ok ? await procRes.json() : { procedures: [] };
      setTasks(tasksData.tasks || []);
      setProcedures(procData.procedures || []);
    } catch (e) {
      console.warn("Tasks/procedures not available:", e);
    } finally {
      setLoadingTasks(false);
    }
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    let active = true;

    const safeLoad = async () => {
      setLoadingTasks(true);
      try {
        const [tasksRes, procRes] = await Promise.all([
          fetch("/api/tasks", { cache: "no-store" }),
          fetch("/api/automation/procedures", { cache: "no-store" }),
        ]);
        if (active && tasksRes.ok) {
          const data = await tasksRes.json();
          setTasks(data.tasks || []);
        }
        if (active && procRes.ok) {
          const data = await procRes.json();
          setProcedures(data.procedures || []);
        }
      } catch (e) {
        console.warn("Tasks/procedures not available:", e);
      } finally {
        if (active) setLoadingTasks(false);
      }
    };
    safeLoad();
    const id = setInterval(safeLoad, 5000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    const tick = () => setTime(new Date().toLocaleTimeString("es-ES"));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!canvasRef.current) return;
    particlesRef.current = new ParticleSystem3D(canvasRef.current);

    let last = performance.now();
    let raf = 0;
    const loop = () => {
      const now = performance.now();
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      particlesRef.current?.update(dt);
      raf = requestAnimationFrame(loop);
    };
    loop();

    return () => {
      cancelAnimationFrame(raf);
      particlesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!particlesRef.current || reducedMotion) return;
    const meta = STATE_META[state];
    particlesRef.current.setMode(meta.mode);
  }, [state, reducedMotion]);

  const addLog = (msg: string) => {
    const ts = new Date().toLocaleTimeString("es-ES");
    setLogs((prev) => {
      const next = [...prev, { ts, msg }];
      return next.slice(-20);
    });
  };

  const meta = STATE_META[state];
  const metrics = [
    { label: "CPU", value: telemetry ? `${telemetry.cpu.toFixed(1)}%` : "—" },
    { label: "Memoria", value: telemetry ? `${telemetry.memory.toFixed(1)}%` : "—" },
    { label: "Disco", value: telemetry ? `${telemetry.disk.toFixed(1)}%` : "—" },
    { label: "Red", value: telemetry ? `${Math.round((telemetry.network.bytes_recv ?? 0) / 1024 / 1024)} MB recibidos` : "—" },
  ];

  const runDiagnostic = async () => {
    setDiagnosing(true);
    addLog("Consultando diagnóstico del sistema...");
    try {
      const response = await fetch("/api/system/telemetry", { cache: "no-store" });
      if (!response.ok) throw new Error(`Telemetry ${response.status}`);
      const data = (await response.json()) as Telemetry;
      setTelemetry(data);
      const warnings = [
        data.cpu > 85 && "CPU alta",
        data.memory > 85 && "Memoria alta",
        data.disk > 90 && "Disco casi lleno",
      ].filter(Boolean) as string[];
      addLog(warnings.length ? `Advertencias: ${warnings.join(", ")}` : "Diagnóstico: sistema estable");
    } catch (error: unknown) {
      console.error("Diagnóstico fallido:", error);
      addLog("Diagnóstico no disponible");
    } finally {
      setDiagnosing(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #05070a 0%, #0f1219 100%)",
        color: "#e6e9f0",
        fontFamily: "'JetBrains Mono', 'Courier New', monospace",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          position: "fixed",
          inset: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
        }}
        aria-hidden="true"
      />

      <div
        style={{
          position: "relative",
          zIndex: 1,
          minHeight: "100vh",
          display: "grid",
          gridTemplateRows: "auto 1fr auto",
          gap: "16px",
          padding: "16px",
        }}
      >
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "12px 16px",
            background: "rgba(15, 18, 25, 0.7)",
            border: "1px solid rgba(124, 77, 255, 0.3)",
            borderRadius: "12px",
            backdropFilter: "blur(12px)",
          }}
        >
          <div>
            <h1 style={{ margin: 0, fontSize: "18px", letterSpacing: "2px" }}>AURA CORE</h1>
            <p style={{ margin: "4px 0 0", opacity: 0.6, fontSize: "11px" }}>v2.1.0 — Núcleo Visual</p>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "20px", fontWeight: 700, letterSpacing: "2px" }}>{time}</div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                marginTop: "4px",
                padding: "4px 10px",
                borderRadius: "20px",
                fontSize: "11px",
                fontWeight: 600,
                background: `${meta.color}18`,
                color: meta.color,
                border: `1px solid ${meta.color}44`,
              }}
            >
              <span
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: meta.color,
                  boxShadow: `0 0 8px ${meta.color}`,
                }}
              />
              {meta.label}
            </div>
          </div>
        </header>

        <main
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 320px",
            gap: "16px",
          }}
        >
          <section
            style={{
              background: "rgba(15, 18, 25, 0.6)",
              border: "1px solid rgba(124, 77, 255, 0.2)",
              borderRadius: "16px",
              padding: "24px",
              backdropFilter: "blur(8px)",
            }}
          >
            <h2 style={{ margin: "0 0 16px", fontSize: "14px", opacity: 0.7, letterSpacing: "1px" }}>PANEL DE CONTROL</h2>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                gap: "12px",
              }}
            >
              {metrics.map((item) => (
                <div
                  key={item.label}
                  style={{
                    padding: "12px",
                    background: "rgba(5, 7, 10, 0.6)",
                    border: "1px solid rgba(124, 77, 255, 0.2)",
                    borderRadius: "10px",
                  }}
                >
                  <div style={{ fontSize: "11px", opacity: 0.6, marginBottom: "4px" }}>{item.label}</div>
                  <div style={{ fontSize: "18px", fontWeight: 700 }}>{item.value}</div>
                </div>
              ))}
            </div>

            <div
              style={{
                marginTop: "16px",
                padding: "12px",
                background: "rgba(5, 7, 10, 0.6)",
                border: "1px solid rgba(124, 77, 255, 0.2)",
                borderRadius: "10px",
              }}
            >
              <div style={{ fontSize: "11px", opacity: 0.6, marginBottom: "8px" }}>ESTADO DEL NÚCLEO</div>
              <div
                style={{
                  height: "4px",
                  borderRadius: "2px",
                  background: `linear-gradient(90deg, ${meta.color}, transparent)`,
                  boxShadow: `0 0 8px ${meta.color}`,
                }}
              />
              <div style={{ marginTop: "8px", fontSize: "12px" }}>{meta.label}</div>
            </div>

            <div
              style={{
                marginTop: "16px",
                padding: "12px",
                background: "rgba(5, 7, 10, 0.6)",
                border: "1px solid rgba(124, 77, 255, 0.2)",
                borderRadius: "10px",
              }}
            >
              <div style={{ fontSize: "11px", opacity: 0.6, marginBottom: "8px" }}>TAREAS Y AUTOMATIZACIONES</div>
              {loadingTasks ? (
                <div style={{ fontSize: "12px", opacity: 0.7 }}>Cargando...</div>
              ) : (
                <div style={{ display: "grid", gap: "8px" }}>
                  {tasks.length === 0 && procedures.length === 0 && (
                    <div style={{ fontSize: "12px", opacity: 0.6 }}>Sin tareas ni procedimientos aprendidos.</div>
                  )}
                  {tasks.slice(0, 5).map((t) => (
                    <div key={String(t.task_id)} style={{ fontSize: "12px", padding: "6px", background: "rgba(124,77,255,0.08)", borderRadius: "6px" }}>
                      <div style={{ fontWeight: 600 }}>{String(t.name || t.task_id)}</div>
                      <div style={{ opacity: 0.7 }}>{String(t.status)} · {t.progress ? `${(Number(t.progress) * 100).toFixed(0)}%` : ""}</div>
                    </div>
                  ))}
                  {procedures.slice(0, 5).map((p) => (
                    <div key={String(p.procedure_id)} style={{ fontSize: "12px", padding: "6px", background: "rgba(0,200,83,0.08)", borderRadius: "6px" }}>
                      <div style={{ fontWeight: 600 }}>{String(p.name)}</div>
                      <div style={{ opacity: 0.7 }}>{String(p.goal)} · ejecutado {Number(p.execution_count ?? 0)} veces</div>
                      <button
                        onClick={async () => {
                          try {
                            const res = await fetch(`/automation/procedures/${p.procedure_id}/run`, { method: "POST" });
                            const data = await res.json();
                            if (res.ok) addLog(`Ejecutando procedimiento: ${p.name} → task ${data.task_id}`);
                            else addLog(`Error ejecutando: ${res.status}`);
                          } catch (e) {
                            addLog(`Fallo ejecución: ${e instanceof Error ? e.message : e}`);
                          }
                          load();
                        }}
                        style={{ marginTop: "4px", padding: "2px 6px", fontSize: "10px", background: "rgba(124,77,255,0.15)", border: "1px solid rgba(124,77,255,0.4)", borderRadius: "4px", color: "#e6e9f0", cursor: "pointer" }}
                      >
                        Ejecutar
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <aside
            style={{
              background: "rgba(15, 18, 25, 0.7)",
              border: "1px solid rgba(124, 77, 255, 0.2)",
              borderRadius: "16px",
              padding: "16px",
              backdropFilter: "blur(12px)",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
            }}
          >
            <h3 style={{ margin: 0, fontSize: "12px", opacity: 0.7, letterSpacing: "1px" }}>TERMINAL</h3>
            <div
              style={{
                flex: 1,
                background: "rgba(5, 7, 10, 0.8)",
                border: "1px solid rgba(124, 77, 255, 0.15)",
                borderRadius: "10px",
                padding: "12px",
                overflowY: "auto",
                maxHeight: "240px",
                fontSize: "11px",
                lineHeight: "1.6",
              }}
            >
              {logs.map((log, i) => (
                <div key={i}>
                  <span style={{ opacity: 0.5 }}>[{log.ts}]</span> {log.msg}
                </div>
              ))}
            </div>
            <button
              onClick={runDiagnostic}
              disabled={diagnosing}
              style={{
                padding: "8px",
                background: "rgba(124, 77, 255, 0.15)",
                border: "1px solid rgba(124, 77, 255, 0.4)",
                color: "#e6e9f0",
                borderRadius: "8px",
                cursor: "pointer",
                fontSize: "12px",
              }}
            >
              {diagnosing ? "Analizando..." : "Ejecutar diagnóstico"}
            </button>
          </aside>
        </main>

        <footer
          style={{
            padding: "8px 16px",
            background: "rgba(15, 18, 25, 0.6)",
            border: "1px solid rgba(124, 77, 255, 0.2)",
            borderRadius: "10px",
            fontSize: "11px",
            opacity: 0.6,
            textAlign: "center",
          }}
        >
          AURA OS v2.1.0 — Modo: {reducedMotion ? "Movimiento reducido" : "Normal"} — Backend: {state === "connected" || state === "delegating" || state === "syncing" ? "Conectado" : "Desconectado"}
        </footer>
      </div>
    </div>
  );
}
