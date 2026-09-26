"use client";
import { use, useState, useEffect, useRef } from "react";
import LocalDB from "@/lib/indexed-db";
import AmestatusSyncManager from "@/lib/ame-sync";
import type { Amestatus } from "@/lib/ame-state-machine";
import ChatIntegration from "@/components/story/ChatIntegration";
import { JJK } from "@/lib/jjk-theme";
import {
  flushPendingEvents,
  getPendingCount,
  isOnline as isNetOnline,
  queueEvent,
} from "@/lib/ame-sync-client";
import {
  getSessionContext,
  getMobileStoryContext,
  listWorks,
  listCharacters,
  bindSession,
  unbindSession,
  checkConsistency,
  StoryApiError,
} from "@/lib/story-client";
import type { StoryWork, StoryCharacter } from "@/lib/story-types";

const BLOCKED_COMMANDS = [
  "rm -rf",
  "format",
  "delete database",
  "drop table",
  "drop database",
];

export default function AMEDetail({
  params,
}: {
  params: Promise<{ ameId: string }>;
}) {
  const { ameId } = use(params);
  const [messages, setMessages] = useState<Array<{ role: string; text: string; timestamp: string }>>([]);
  const [input, setInput] = useState("");
  const [connectionStatus, setConnectionStatus] = useState<Amestatus>("independent");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [storyPanelOpen, setStoryPanelOpen] = useState(false);
  const [works, setWorks] = useState<StoryWork[]>([]);
  const [characters, setCharacters] = useState<StoryCharacter[]>([]);
  const [selectedWork, setSelectedWork] = useState("");
  const [selectedChar, setSelectedChar] = useState("");
  const [contextActive, setContextActive] = useState(false);
  const [coherenceStatus, setCoherenceStatus] = useState<"idle" | "pass" | "fail">("idle");
  const [storyError, setStoryError] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [pendingSync, setPendingSync] = useState<number>(0);

  // Monitor de conectividad + auto-sync al volver online.
  useEffect(() => {
    const update = () => setIsOnline(isNetOnline());
    update();
    const onOnline = async () => {
      setIsOnline(true);
      try {
        const result = await flushPendingEvents();
        if (result) setPendingSync(0);
      } catch {
        /* se reintenta en el próximo online */
      }
    };
    window.addEventListener("offline", () => setIsOnline(false));
    window.addEventListener("online", onOnline);
    return () => {
      window.removeEventListener("offline", () => setIsOnline(false));
      window.removeEventListener("online", onOnline);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const loadHistory = async () => {
      try {
        const history = await LocalDB.getInstance().getChatHistory(ameId);
        setMessages(history || []);
      } catch (err) {
        console.warn("No se pudo cargar historial:", err);
      }
    };

    const syncManager = AmestatusSyncManager.getInstance();
    syncManager.init().catch((err) => console.error("No se pudo iniciar sincronización AME:", err));

    const unsubscribe = syncManager.subscribe((state) => {
      setConnectionStatus(state.ameStatus);
    });

    loadHistory();
    void getPendingCount().then((n) => setPendingSync(n));
    const pendingTimer = setInterval(() => {
      void getPendingCount().then((n) => setPendingSync(n));
    }, 5000);

    const loadStoryContext = async () => {
      try {
        const ctxRes = await getMobileStoryContext(ameId);
        setContextActive(ctxRes.active);
        if (ctxRes.active) {
          setSelectedWork(ctxRes.work_id ?? "");
          setSelectedChar(ctxRes.character_id ?? "");
        }
      } catch {
        setStoryError("No se pudo cargar el contexto literario");
      }

      try {
        const worksRes = await listWorks();
        setWorks(worksRes.works || []);
      } catch {
        setStoryError("No se pudieron cargar las obras");
      }
    };

    loadStoryContext();

    return () => {
      unsubscribe();
      syncManager.destroy();
    };
  }, [ameId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!selectedWork) {
      setCharacters([]);
      setSelectedChar("");
      return;
    }
    let cancelled = false;
    listCharacters(selectedWork)
      .then((res) => {
        if (!cancelled) {
          setCharacters(res.characters || []);
          if (res.characters?.length > 0) setSelectedChar(res.characters[0].char_id);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedWork]);

  const handleBindSession = async () => {
    if (!selectedWork || !selectedChar) return;
    try {
      await bindSession(ameId, {
        work_id: selectedWork,
        character_id: selectedChar,
      });
      setContextActive(true);
      setStoryError(null);
    } catch (err: unknown) {
      const msg = err instanceof StoryApiError ? err.message : "Error al vincular sesión";
      setStoryError(msg);
    }
  };

  const handleUnbindSession = async () => {
    try {
      await unbindSession(ameId);
      setContextActive(false);
      setSelectedWork("");
      setSelectedChar("");
    } catch {
      setStoryError("Error al desvincular sesión");
    }
  };

  const handleCheckConsistency = async (text: string) => {
    if (!selectedWork || !selectedChar || !text.trim()) return;
    try {
      const res = await checkConsistency(selectedWork, selectedChar, text.trim());
      setCoherenceStatus(res.overall_pass ? "pass" : "fail");
    } catch {
      setCoherenceStatus("idle");
    }
  };

  const handleWorkChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedWork(e.target.value);
    setSelectedChar("");
    setCharacters([]);
  };

  const handleCharChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedChar(e.target.value);
  };

  const isCommandSafe = (text: string): boolean => {
    const lower = text.toLowerCase();
    return !BLOCKED_COMMANDS.some((cmd) => lower.includes(cmd));
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;

    if (!isCommandSafe(text)) {
      alert("Comando bloqueado por seguridad.");
      return;
    }

    setSending(true);
    const timestamp = new Date().toISOString();

    const userMessage = { role: "user", text, timestamp };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    try {
      await LocalDB.getInstance().saveChatMessage({ role: "user", text, ameId });
    } catch (err) {
      console.warn("Error guardando mensaje local:", err);
    }

    const syncManager = AmestatusSyncManager.getInstance();
    const isAuraOnline = syncManager.isOnline();

    if (isAuraOnline) {
      try {
        const response = await fetch("/api/mobile/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ameId, message: text }),
        });
        if (!response.ok) throw new Error(`Chat API HTTP ${response.status}`);
        const data = await response.json() as { response?: string; ameResponse?: string; text?: string };
        const responseText = data.response ?? data.ameResponse ?? data.text;
        if (!responseText) throw new Error("La respuesta de AURA no contiene texto");
        const ameMessage = { role: "ame", text: responseText, timestamp: new Date().toISOString() };
        setMessages((prev) => [...prev, ameMessage]);
        await LocalDB.getInstance().saveChatMessage({ role: "ame", text: responseText, ameId });
        if (contextActive && selectedWork && selectedChar) {
          void handleCheckConsistency(responseText);
        }
      } catch (err) {
        console.error("Error enviando mensaje a AURA:", err);
        await syncManager.queueEvent("chat_message", {
          ameId,
          role: "user",
          content: text,
          timestamp: new Date().toISOString(),
        } as Record<string, unknown>);
        const errorMessage = { role: "system", text: "No se pudo contactar AURA. El mensaje queda guardado para reintento.", timestamp: new Date().toISOString() };
        setMessages((prev) => [...prev, errorMessage]);
      }
    } else {
      const syncManager = AmestatusSyncManager.getInstance();
      await syncManager.queueEvent("chat_message", {
        ameId,
        role: "user",
        content: text,
        timestamp: new Date().toISOString(),
      } as Record<string, unknown>);
      const offlineMessage = { role: "system", text: "Mensaje guardado. Se enviará cuando AURA esté disponible.", timestamp };
      setMessages((prev) => [...prev, offlineMessage]);
    }

    setSending(false);
  };

  const getConnectionLabel = () => {
    switch (connectionStatus) {
      case "connected":
        return { text: "Conectado a AURA", color: "#00C853", bg: "rgba(0,200,83,0.12)" };
      case "independent":
        return { text: "AURA PC desconectada — mensajes guardados localmente", color: "#FFD700", bg: "rgba(255,215,0,0.12)" };
      case "offline_pending":
        return { text: "Sin conexión a Internet", color: "#DC143C", bg: "rgba(220,20,60,0.12)" };
      case "reconnecting":
        return { text: "Reconectando...", color: "#00e5ff", bg: "rgba(0,229,255,0.12)" };
      case "syncing":
        return { text: "Sincronizando...", color: "#7c4dff", bg: "rgba(124,77,255,0.12)" };
      case "auth_failed":
        return { text: "Error de autenticación — reconectar desde AURA Core", color: "#DC143C", bg: "rgba(220,20,60,0.12)" };
      default:
        return { text: "Estado desconocido", color: "#aaa", bg: "rgba(255,255,255,0.05)" };
    }
  };

  const conn = getConnectionLabel();

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #080408 0%, #1a1a2e 100%)",
        color: "#F0F0F8",
        padding: "20px",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <button
        onClick={() => (window.location.href = "/ame")}
        style={{
          background: "#DC143C",
          color: "#F0F0F8",
          border: "none",
          padding: "10px 20px",
          borderRadius: "4px",
          cursor: "pointer",
          marginBottom: "20px",
        }}
      >
        ← Atrás
      </button>

      <div
        style={{
          marginBottom: "20px",
          padding: "10px 16px",
          background: conn.bg,
          color: conn.color,
          border: `1px solid ${conn.color}33`,
          borderRadius: "8px",
          fontWeight: "bold",
          display: "inline-flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <span
          style={{
            width: "10px",
            height: "10px",
            borderRadius: "50%",
            background: conn.color,
            boxShadow: `0 0 10px ${conn.color}`,
          }}
        />
        {conn.text}
      </div>

      {/* Indicador offline-first: conectividad + eventos pendientes de sync */}
      <div
        className="text-xs mb-2 inline-flex items-center gap-2 px-2 py-1 rounded"
        style={{
          background: isOnline ? "rgba(0,200,83,0.10)" : "rgba(255,215,0,0.10)",
          color: isOnline ? "#00e5ff" : "#FFD700",
          border: `1px solid ${isOnline ? "#00e5ff33" : "#FFD70033"}`,
        }}
      >
        {isOnline ? "🟢 Online" : "🟡 Offline — buffer activo"}
        <span style={{ opacity: 0.7 }}>
          · {pendingSync} pendientes
        </span>
      </div>

      <ChatIntegration sessionId={ameId} />

      <div style={{ marginBottom: "12px" }}>
        <button
          onClick={() => setStoryPanelOpen((v) => !v)}
          style={{
            background: JJK.ACCENT,
            color: "#fff",
            border: "none",
            padding: "8px 14px",
            borderRadius: "6px",
            cursor: "pointer",
            fontSize: "13px",
            fontWeight: "bold",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          {storyPanelOpen ? "▲ Contexto Literario" : "▼ Contexto Literario"}
        </button>
        {contextActive && (
          <span
            style={{
              marginLeft: "8px",
              fontSize: "12px",
              color: "#00e5ff",
            }}
          >
            🟢 Activo
          </span>
        )}
        {coherenceStatus === "pass" && (
          <span style={{ marginLeft: "8px", fontSize: "12px", color: "#00e5ff" }}>✅ Coherente</span>
        )}
        {coherenceStatus === "fail" && (
          <span style={{ marginLeft: "8px", fontSize: "12px", color: "#ff4d4d" }}>🚨 Incoherente</span>
        )}
      </div>

      {storyPanelOpen && (
        <div
          style={{
            background: JJK.PANEL,
            border: `1px solid ${JJK.ACCENT}33`,
            borderRadius: "8px",
            padding: "12px",
            marginBottom: "16px",
          }}
        >
          {works.length === 0 ? (
            <p style={{ color: `${JJK.TEXT}99`, fontSize: "12px" }}>No hay obras disponibles.</p>
          ) : (
            <>
              <select
                value={selectedWork}
                onChange={handleWorkChange}
                style={{
                  width: "100%",
                  padding: "8px",
                  marginBottom: "8px",
                  background: JJK.BG,
                  color: JJK.TEXT,
                  border: `1px solid ${JJK.ACCENT}33`,
                  borderRadius: "4px",
                  fontSize: "13px",
                  boxSizing: "border-box",
                }}
              >
                <option value="">— seleccionar obra —</option>
                {works.map((w) => (
                  <option key={w.work_id} value={w.work_id}>
                    {w.title}
                  </option>
                ))}
              </select>
              <select
                value={selectedChar}
                onChange={handleCharChange}
                disabled={!selectedWork || characters.length === 0}
                style={{
                  width: "100%",
                  padding: "8px",
                  marginBottom: "8px",
                  background: JJK.BG,
                  color: JJK.TEXT,
                  border: `1px solid ${JJK.ACCENT}33`,
                  borderRadius: "4px",
                  fontSize: "13px",
                  boxSizing: "border-box",
                }}
              >
                {characters.length === 0 ? (
                  <option value="">— sin personajes —</option>
                ) : (
                  characters.map((c) => (
                    <option key={c.char_id} value={c.char_id}>
                      {c.name}
                    </option>
                  ))
                )}
              </select>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <button
                  onClick={handleBindSession}
                  disabled={!selectedWork || !selectedChar || contextActive}
                  style={{
                    flex: 1,
                    background: JJK.ACCENT,
                    color: "#fff",
                    border: "none",
                    padding: "8px",
                    borderRadius: "4px",
                    cursor: !selectedWork || !selectedChar || contextActive ? "not-allowed" : "pointer",
                    fontSize: "12px",
                    opacity: !selectedWork || !selectedChar || contextActive ? 0.5 : 1,
                  }}
                >
                  Vincular
                </button>
                <button
                  onClick={handleUnbindSession}
                  disabled={!contextActive}
                  style={{
                    flex: 1,
                    background: "transparent",
                    color: JJK.TEXT,
                    border: `1px solid ${JJK.ACCENT}55`,
                    padding: "8px",
                    borderRadius: "4px",
                    cursor: !contextActive ? "not-allowed" : "pointer",
                    fontSize: "12px",
                    opacity: !contextActive ? 0.5 : 1,
                  }}
                >
                  Desvincular
                </button>
              </div>
            </>
          )}
          {storyError && (
            <p style={{ color: JJK.RED, fontSize: "11px", marginTop: "6px" }}>
              ⚠ {storyError}
            </p>
          )}
        </div>
      )}

      <div
        style={{
          width: "120px",
          height: "120px",
          background: "#1a1a2e",
          border: "3px solid #FFD700",
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "60px",
          margin: "20px 0",
        }}
      >
        🤖
      </div>

       <h1 style={{ fontSize: "28px", margin: "0 0 10px 0" }}>AME {ameId}</h1>
       <div style={{ margin: "0 0 20px 0", display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
         <p style={{ margin: 0 }}>
           Estado: <span style={{ color: "#FFD700" }}>● Activo</span>
         </p>
         <span
           style={{
             fontSize: "12px",
             padding: "3px 10px",
             borderRadius: "12px",
             background: isOnline && connectionStatus === "connected"
               ? "rgba(0,200,83,0.15)"
               : "rgba(255,215,0,0.1)",
             color: isOnline && connectionStatus === "connected" ? "#00C853" : "#FFD700",
             border: `1px solid ${isOnline && connectionStatus === "connected" ? "rgba(0,200,83,0.4)" : "rgba(255,215,0,0.3)"}`,
           }}
         >
           {isOnline && connectionStatus === "connected"
             ? "🟢 En línea (SD sincronizada)"
             : "🟡 Offline — cambios en SD local"}
         </span>
         {pendingSync > 0 && (
           <span
             style={{
               fontSize: "11px",
               padding: "3px 8px",
               borderRadius: "10px",
               background: "rgba(220,20,60,0.15)",
               color: "#FF6B6B",
               border: "1px solid rgba(220,20,60,0.4)",
             }}
           >
             {pendingSync} pendientes en SD
           </span>
         )}
       </div>

      <div
        style={{
          background: "#1a1a2e",
          border: "1px solid #DC143C",
          borderRadius: "8px",
          padding: "20px",
          marginTop: "20px",
          minHeight: "300px",
        }}
      >
        <h3 style={{ margin: "0 0 15px 0" }}>Chat</h3>
        <div
          style={{
            background: "#080408",
            padding: "15px",
            borderRadius: "4px",
            marginTop: "10px",
            minHeight: "200px",
            maxHeight: "400px",
            overflowY: "auto",
          }}
        >
          {messages.length === 0 && (
            <p style={{ opacity: 0.7 }}>Sin mensajes. Escribe algo para comenzar.</p>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              style={{
                marginBottom: "10px",
                padding: "8px 12px",
                background: msg.role === "user" ? "rgba(124,77,255,0.15)" : msg.role === "system" ? "rgba(255,215,0,0.08)" : "rgba(0,200,83,0.08)",
                border: `1px solid ${msg.role === "user" ? "rgba(124,77,255,0.3)" : msg.role === "system" ? "rgba(255,215,0,0.2)" : "rgba(0,200,83,0.2)"}`,
                borderRadius: "6px",
                fontSize: "14px",
              }}
            >
              <div style={{ fontSize: "11px", opacity: 0.6, marginBottom: "4px" }}>
                {msg.role === "user" ? "Tú" : msg.role === "ame" ? "AME" : "Sistema"} — {new Date(msg.timestamp).toLocaleTimeString("es-ES")}
              </div>
              <div>{msg.text}</div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSend();
            }}
            placeholder="Escribe tu mensaje..."
            disabled={sending}
            style={{
              flex: 1,
              padding: "10px",
              background: "#080408",
              color: "#F0F0F8",
              border: "1px solid #DC143C",
              borderRadius: "4px",
              boxSizing: "border-box",
              opacity: sending ? 0.7 : 1,
            }}
          />
          <button
            onClick={handleSend}
            disabled={sending}
            style={{
              background: "#DC143C",
              color: "#F0F0F8",
              border: "none",
              padding: "10px 20px",
              borderRadius: "4px",
              cursor: sending ? "not-allowed" : "pointer",
              fontWeight: "bold",
            }}
          >
            {sending ? "..." : "Enviar"}
          </button>
        </div>
      </div>
    </div>
  );
}
