"use client";

import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

type Result = { ok: boolean; message: string; data?: string };
type Payload = Record<string, unknown>;

const card: CSSProperties = {
  background: "#1a1a2e",
  border: "2px solid #DC143C",
  borderRadius: 12,
  padding: 16,
  marginBottom: 16,
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
const btn: CSSProperties = {
  background: "linear-gradient(135deg,#DC143C,#FF1744)",
  color: "#F0F0F8",
  border: "none",
  padding: "10px 16px",
  borderRadius: 8,
  marginRight: 8,
  cursor: "pointer",
  fontWeight: "bold",
};

export default function BrowserControlPage() {
  const [url, setUrl] = useState("");
  const [selector, setSelector] = useState("");
  const [fillValue, setFillValue] = useState("");
  const [log, setLog] = useState<string[]>([]);
  const [device, setDevice] = useState("Sin conexion");

  const push = (line: string) => setLog((prev) => [line, ...prev].slice(0, 60));

  useEffect(() => {
    const ch = new BroadcastChannel("aura-device-app");
    ch.onmessage = async (ev: MessageEvent) => {
      const msg = ev.data as {
        type?: string;
        id?: string;
        action?: string;
        payload?: Payload;
      };
      if (msg?.type === "command" && msg.action) {
        const res = await runAction(msg.action, msg.payload ?? {});
        ch.postMessage({ type: "result", id: msg.id, result: res });
      }
    };
    ch.postMessage({ type: "agent-ready" });
    setDevice("Conectado via BroadcastChannel");
    return () => ch.close();
  }, []);

  const runAction = async (action: string, p: Payload): Promise<Result> => {
    try {
      switch (action) {
        case "navigate":
          window.location.href = String(p.url ?? "");
          return { ok: true, message: `Navegando a ${String(p.url)}` };
        case "back":
          window.history.back();
          return { ok: true, message: "Atras" };
        case "reload":
          window.location.reload();
          return { ok: true, message: "Recargado" };
        case "extractText": {
          const el = p.selector ? document.querySelector(String(p.selector)) : null;
          const text = el ? el.textContent : document.body.innerText;
          return { ok: true, message: "Texto extraido", data: (text ?? "").slice(0, 3000) };
        }
        case "click": {
          const el = document.querySelector(String(p.selector));
          if (!el) return { ok: false, message: `No encontrado: ${String(p.selector)}` };
          (el as HTMLElement).click();
          return { ok: true, message: `Clic en ${String(p.selector)}` };
        }
        case "fill": {
          const el = document.querySelector(String(p.selector)) as HTMLInputElement | null;
          if (!el) return { ok: false, message: `No encontrado: ${String(p.selector)}` };
          el.value = String(p.value ?? "");
          el.dispatchEvent(new Event("input", { bubbles: true }));
          return { ok: true, message: `Rellenado ${String(p.selector)}` };
        }
        default:
          return { ok: false, message: `Accion desconocida: ${action}` };
      }
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : String(e) };
    }
  };

  const exec = async (action: string, payload: Payload) => {
    const r = await runAction(action, payload);
    push(`${r.ok ? "✅" : "❌"} ${r.message}`);
  };

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg,#080408 0%,#1a1a2e 100%)",
        color: "#F0F0F8",
        padding: "24px",
      }}
    >
      <h1 style={{ fontSize: "28px", margin: "0 0 4px" }}>
        🕹️ AURA/AME — Control de Navegador
      </h1>
      <p style={{ opacity: 0.7, marginTop: 0 }}>
        Habilidad que da a AURA/AME control sobre el navegador donde se ejecuta.
      </p>
      <p style={{ opacity: 0.8 }}>
        Estado app del dispositivo: <b>{device}</b>
      </p>

      <section style={card}>
        <h3>Navegacion</h3>
        <input
          placeholder="https://..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          style={inputStyle}
        />
        <button style={btn} onClick={() => exec("navigate", { url })}>
          Ir
        </button>
        <button style={btn} onClick={() => exec("back", {})}>
          Atras
        </button>
        <button style={btn} onClick={() => exec("reload", {})}>
          Recargar
        </button>
      </section>

      <section style={card}>
        <h3>Interaccion DOM</h3>
        <input
          placeholder="selector CSS (ej. #id, .class)"
          value={selector}
          onChange={(e) => setSelector(e.target.value)}
          style={inputStyle}
        />
        <button style={btn} onClick={() => exec("extractText", { selector })}>
          Extraer texto
        </button>
        <button style={btn} onClick={() => exec("click", { selector })}>
          Clic
        </button>
        <div style={{ marginTop: 8 }}>
          <input
            placeholder="valor a rellenar"
            value={fillValue}
            onChange={(e) => setFillValue(e.target.value)}
            style={inputStyle}
          />
          <button
            style={btn}
            onClick={() => exec("fill", { selector, value: fillValue })}
          >
            Rellenar
          </button>
        </div>
      </section>

      <section style={card}>
        <h3>Log de acciones</h3>
        <pre
          style={{
            whiteSpace: "pre-wrap",
            background: "#080408",
            padding: 12,
            borderRadius: 8,
            maxHeight: 300,
            overflow: "auto",
          }}
        >
          {log.join("\n") || "Sin acciones aun."}
        </pre>
      </section>

      <p style={{ opacity: 0.6, fontSize: 12 }}>
        Conexion con app del dispositivo via{" "}
        <code>BroadcastChannel(&quot;aura-device-app&quot;)</code>: la app puede
        enviar {"{type:'command', action, payload}"} y recibe{" "}
        {"{type:'result', result}"}. El control avanzado (Playwright headless)
        se expone en <code>/api/skills/browser-control</code> en el backend AME.
      </p>
    </main>
  );
}
