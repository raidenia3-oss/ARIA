"use client";
import { useState, useEffect, useRef } from "react";
import AmestatusSyncManager from "@/lib/ame-sync";
import type { Amestatus } from "@/lib/ame-state-machine";
import { saveManualHost, clearManualHost, tryManualHost } from "@/lib/ame-mdns";
import SecureVault, { type VaultWriter, type VaultReader } from "@/lib/secure-vault";
import useVoiceInput from "@/lib/voice-input";

const DEMO_AMES = [
  {
    id: "ame_core",
    name: "AURA-Core",
    status: "online" as const,
    lastActivity: new Date().toISOString(),
    unreadCount: 0,
  },
  {
    id: "ame_analytics",
    name: "Analytics-AME",
    status: "offline" as const,
    lastActivity: new Date(Date.now() - 3600000).toISOString(),
    unreadCount: 2,
  },
  {
    id: "ame_integrations",
    name: "Integrations-AME",
    status: "online" as const,
    lastActivity: new Date(Date.now() - 7200000).toISOString(),
    unreadCount: 0,
  },
  {
    id: "ame_monitor",
    name: "Monitor-AME",
    status: "online" as const,
    lastActivity: new Date(Date.now() - 1800000).toISOString(),
    unreadCount: 5,
  },
  {
    id: "ame_learning",
    name: "Learning-AME",
    status: "offline" as const,
    lastActivity: new Date(Date.now() - 86400000).toISOString(),
    unreadCount: 0,
  },
];

export default function AMEDashboard() {
  const [ames, setAmes] = useState(DEMO_AMES);
  const [apiAvailable, setApiAvailable] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<Amestatus>("independent");
  const [realtimeStatus, setRealtimeStatus] = useState<"live" | "buffered" | "offline">("offline");
  const [latestEvent, setLatestEvent] = useState<string | null>(null);
  const [manualHost, setManualHost] = useState("");
  const [showManualInput, setShowManualInput] = useState(false);
  const vaultRef = useRef<SecureVault | null>(null);
  const [vaultStatus, setVaultStatus] = useState<{ locked: boolean; lockSecs: number; secondsUntilLock: number }>(
    { locked: true, lockSecs: 900, secondsUntilLock: 0 },
  );
  const [vaultPass, setVaultPass] = useState("");
  const [vaultError, setVaultError] = useState<string | null>(null);
  if (!vaultRef.current) vaultRef.current = new SecureVault({ lockSecs: 900 });

  useEffect(() => {
    if (typeof window === "undefined") return;

    const syncManager = AmestatusSyncManager.getInstance();
    syncManager.init().catch((err) => console.error("No se pudo iniciar sincronización AME:", err));

    const unsubscribe = syncManager.subscribe((state) => {
      setConnectionStatus(state.ameStatus);
      setRealtimeStatus(state.realtimeStatus);
    });

    const realtimeUnsub = syncManager.subscribeRealtime((event) => {
      let label = "";
      switch (event.type) {
        case "canon_event":
          label = `Canon: ${event.payload.description?.slice(0, 60) ?? ""}`;
          break;
        case "character_update":
          label = `Personaje actualizado: ${event.payload.char_id}`;
          break;
        case "session_change":
          label = `Sesión: ${event.payload.status}`;
          break;
        case "reflection":
          label = `Reflexión: ${event.payload.work_id}`;
          break;
        case "plot_summary":
          label = `Resumen: ${event.payload.work_id}`;
          break;
      }
      setLatestEvent(label);
    });

    syncManager.subscribeRealtimeWork("default");

    return () => {
      unsubscribe();
      realtimeUnsub();
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    fetch("/api/mobile/ames")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setAmes(data.ames || []);
        setApiAvailable(true);
      })
      .catch((err) => {
        console.warn("API /api/mobile/ames no disponible:", err.message || err);
        setAmes(DEMO_AMES);
        setApiAvailable(false);
      });
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const refreshVault = () => {
      const v = vaultRef.current;
      if (v) {
        setVaultStatus({ locked: v.isLocked, lockSecs: vaultStatus.lockSecs, secondsUntilLock: v.secondsUntilLock });
      }
    };
    refreshVault();
    const t = setInterval(refreshVault, 3000);
    return () => clearInterval(t);
  }, []);

  const handleUnlockVault = async () => {
    setVaultError(null);
    try {
      await vaultRef.current!.unlock(vaultPass);
      setVaultStatus({ locked: false, lockSecs: vaultStatus.lockSecs, secondsUntilLock: vaultRef.current!.secondsUntilLock });
      setVaultPass("");
    } catch (err) {
      setVaultError(err instanceof Error ? err.message : "Error al desbloquear");
    }
  };

  const handleLockVault = () => {
    vaultRef.current!.lock();
    setVaultStatus({ locked: true, lockSecs: vaultStatus.lockSecs, secondsUntilLock: 0 });
  };

  const handleSaveEncryptedNote = async () => {
    setVaultError(null);
    try {
      await vaultRef.current!.unlock(vaultPass || "default-session-key");
      const mockWriter: VaultWriter = async (name, blob) => {
        // Simula la SD: persiste el blob cifrado en localStorage.
        localStorage.setItem(`aura_vault_${name}`, blob);
      };
      await vaultRef.current!.saveToStorage("writer_notes", JSON.stringify({ notes: "Notas confidenciales de la Character Bible" }), mockWriter);
      setVaultStatus({ locked: false, lockSecs: vaultStatus.lockSecs, secondsUntilLock: vaultRef.current!.secondsUntilLock });
    } catch (err) {
      setVaultError(err instanceof Error ? err.message : "Error al guardar");
    }
  };

  const [voiceText, setVoiceText] = useState<string>("");
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const voiceInput = useVoiceInput();
  const voiceStatusLabel =
    voiceInput.state === "recording"
      ? "Grabando… suelta para transcribir"
      : voiceInput.state === "transcribing"
        ? "Transcribiendo localmente (Whisper)…"
        : "Listo para grabar";

  const handleVoiceToggle = async () => {
    if (voiceInput.state === "recording") {
      await voiceInput.stopRecording();
      const r = voiceInput.result;
      if (r?.text) setVoiceText(r.text);
      if (voiceInput.error) setVoiceError(voiceInput.error);
    } else {
      if (voiceInput.error) setVoiceError(null);
      await voiceInput.startRecording();
      if (voiceInput.error) setVoiceError(voiceInput.error);
    }
  };

  const getConnectionLabel = () => {
    switch (connectionStatus) {
      case "connected":
        return { text: "Conectado a AURA", color: "#00C853", bg: "rgba(0,200,83,0.12)", border: "rgba(0,200,83,0.4)" };
      case "independent":
        return { text: "AURA PC desconectada", color: "#FFD700", bg: "rgba(255,215,0,0.12)", border: "rgba(255,215,0,0.4)" };
      case "offline_pending":
        return { text: "Sin conexión a Internet", color: "#DC143C", bg: "rgba(220,20,60,0.12)", border: "rgba(220,20,60,0.4)" };
      case "reconnecting":
        return { text: "Reconectando...", color: "#00e5ff", bg: "rgba(0,229,255,0.12)", border: "rgba(0,229,255,0.4)" };
      case "syncing":
        return { text: "Sincronizando...", color: "#7c4dff", bg: "rgba(124,77,255,0.12)", border: "rgba(124,77,255,0.4)" };
      case "auth_failed":
        return { text: "Error de autenticación", color: "#DC143C", bg: "rgba(220,20,60,0.12)", border: "rgba(220,20,60,0.4)" };
      default:
        return { text: "Estado desconocido", color: "#aaa", bg: "rgba(255,255,255,0.05)", border: "rgba(255,255,255,0.2)" };
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
      }}
    >
      <div
        style={{
          marginBottom: "40px",
          paddingBottom: "20px",
          borderBottom: "2px solid #DC143C",
        }}
      >
        <h1 style={{ fontSize: "36px", margin: "0 0 10px 0" }}>
          AME Dashboard
        </h1>

        <div
          style={{
            marginTop: "15px",
            padding: "10px 16px",
            background: conn.bg,
            color: conn.color,
            border: `1px solid ${conn.border}`,
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

        {!apiAvailable && (
          <div
            style={{
              marginTop: "12px",
              padding: "10px 16px",
              background: "rgba(255,215,0,0.08)",
              color: "#FFD700",
              border: "1px solid rgba(255,215,0,0.3)",
              borderRadius: "8px",
              fontSize: "14px",
            }}
          >
            Modo demostración — AURA no disponible
          </div>
        )}

        {(connectionStatus === "reconnecting" || connectionStatus === "independent") && !apiAvailable && (
          <div style={{ marginTop: "12px" }}>
            {showManualInput ? (
              <div
                style={{
                  padding: "12px 16px",
                  background: "rgba(120,120,255,0.08)",
                  border: "1px solid rgba(120,120,255,0.3)",
                  borderRadius: "8px",
                }}
              >
                <input
                  type="text"
                  value={manualHost}
                  onChange={(e) => setManualHost(e.target.value)}
                  placeholder="192.168.1.50:8000 o Tailscale IP"
                  style={{
                    background: "rgba(0,0,0,0.5)",
                    border: "1px solid #7c4dff",
                    color: "#fff",
                    padding: "8px",
                    borderRadius: "4px",
                    width: "100%",
                    marginBottom: "8px",
                  }}
                />
                <button
                  onClick={() => {
                    const host = manualHost.trim();
                    if (host) {
                      saveManualHost(host);
                      location.reload();
                    }
                  }}
                  style={{
                    background: "#7c4dff",
                    color: "#fff",
                    border: "none",
                    padding: "8px 16px",
                    borderRadius: "4px",
                    cursor: "pointer",
                    width: "100%",
                  }}
                >
                  Conectar manualmente (fallback)
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowManualInput(true)}
                style={{
                  background: "rgba(220,20,60,0.15)",
                  color: "#DC143C",
                  border: "1px solid #DC143C",
                  padding: "8px 16px",
                  borderRadius: "4px",
                  cursor: "pointer",
                  fontSize: "13px",
                }}
              >
                Introducir IP manual (revisar en AURA PC)
              </button>
            )}
          </div>
        )}

        <div
          style={{
            marginTop: "12px",
            padding: "10px 16px",
            background: realtimeStatus === "live"
              ? "rgba(0,200,83,0.12)"
              : realtimeStatus === "buffered"
                ? "rgba(255,215,0,0.08)"
                : "rgba(220,20,60,0.12)",
            color: realtimeStatus === "live"
              ? "#00C853"
              : realtimeStatus === "buffered"
                ? "#FFD700"
                : "#DC143C",
            border: `1px solid ${realtimeStatus === "live" ? "rgba(0,200,83,0.4)" : realtimeStatus === "buffered" ? "rgba(255,215,0,0.3)" : "rgba(220,20,60,0.4)"}`,
            borderRadius: "8px",
            fontSize: "14px",
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: realtimeStatus === "live"
                ? "#00C853"
                : realtimeStatus === "buffered"
                  ? "#FFD700"
                  : "#DC143C",
              boxShadow: realtimeStatus === "live" ? `0 0 8px #00C853` : "none",
            }}
          />
          {realtimeStatus === "live"
            ? "Eventos en tiempo real activos"
            : realtimeStatus === "buffered"
              ? "Eventos en buffer (reconexión)"
              : "Sin conexión en tiempo real"}
          {latestEvent && (
            <span style={{ opacity: 0.8, marginLeft: "8px" }}>— {latestEvent}</span>
          )}
        </div>
        <div
          style={{
            marginTop: "16px",
            padding: "14px 20px",
            background: "rgba(40, 40, 80, 0.4)",
            border: "1px solid rgba(124, 77, 255, 0.4)",
            borderRadius: "10px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: vaultStatus.locked ? "#DC143C" : "#00C853",
              }}
            />
            <strong style={{ fontSize: "14px" }}>
              {vaultStatus.locked ? "Bloqueada" : "Activada"} Bóveda Literaria (SD)
            </strong>
            {!vaultStatus.locked && (
              <span style={{ fontSize: "12px", opacity: 0.7 }}>
                (auto-lock en {vaultStatus.secondsUntilLock}s)
              </span>
            )}
          </div>
          {vaultStatus.locked ? (
            <>
              <input
                type="password"
                value={vaultPass}
                onChange={(e) => setVaultPass(e.target.value)}
                placeholder="Secreto maestro (no se persiste en texto plano)"
                style={{
                  background: "rgba(0,0,0,0.5)",
                  border: "1px solid #7c4dff",
                  color: "#fff",
                  padding: "8px",
                  borderRadius: "4px",
                  width: "100%",
                  marginBottom: "8px",
                  fontSize: "13px",
                }}
                onKeyDown={(e) => e.key === "Enter" && handleUnlockVault()}
              />
              <button
                onClick={handleUnlockVault}
                style={{
                  background: "#7c4dff",
                  color: "#fff",
                  border: "none",
                  padding: "8px 16px",
                  borderRadius: "4px",
                  cursor: "pointer",
                  fontSize: "13px",
                  width: "100%",
                }}
              >
                Desbloquear bóveda (AES-256-GCM)
              </button>
            </>
          ) : (
            <button
              onClick={handleLockVault}
              style={{
                background: "rgba(220,20,60,0.15)",
                color: "#DC143C",
                border: "1px solid #DC143C",
                padding: "8px 16px",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "13px",
                width: "100%",
              }}
            >
              Cerrar sesión de bóveda
            </button>
          )}
          {vaultError && <p style={{ color: "#DC143C", fontSize: "12px", marginTop: "6px" }}>{vaultError}</p>}
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "20px",
          marginBottom: "40px",
        }}
      >
        {ames.map((ame) => (
          <button
            key={ame.id}
            type="button"
            onClick={() => (window.location.href = `/ame/${ame.id}`)}
            style={{
              background: "#1a1a2e",
              border: "2px solid #DC143C",
              borderRadius: "12px",
              padding: "25px",
              cursor: "pointer",
              transition: "all 0.3s ease",
              position: "relative",
              overflow: "hidden",
              width: "100%",
              textAlign: "left",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "#FFD700";
              e.currentTarget.style.boxShadow = "0 0 20px rgba(255,215,0,0.3)";
              e.currentTarget.style.transform = "translateY(-5px)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "#DC143C";
              e.currentTarget.style.boxShadow = "none";
              e.currentTarget.style.transform = "translateY(0)";
            }}
          >
            <div style={{ position: "relative", zIndex: 1 }}>
              <h3
                style={{
                  margin: "0 0 15px 0",
                  fontSize: "20px",
                  fontWeight: "bold",
                }}
              >
                {ame.name}
              </h3>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "15px",
                  marginBottom: "15px",
                }}
              >
                <div>
                  <p
                    style={{
                      margin: "0 0 5px 0",
                      opacity: 0.7,
                      fontSize: "12px",
                    }}
                  >
                    Estado
                  </p>
                  <p style={{ margin: "0", fontWeight: "bold" }}>
                    <span
                      style={{
                        color: ame.status === "online" ? "#00C853" : "#FFD700",
                      }}
                    >
                      {ame.status === "online" ? "En línea" : "Sin conexión"}
                    </span>
                  </p>
                </div>
                <div>
                  <p
                    style={{
                      margin: "0 0 5px 0",
                      opacity: 0.7,
                      fontSize: "12px",
                    }}
                  >
                    Sin leer
                  </p>
                  <p style={{ margin: "0", fontWeight: "bold" }}>
                    {ame.unreadCount}
                  </p>
                </div>
              </div>
              <p
                style={{
                  margin: "0",
                  opacity: 0.6,
                  fontSize: "12px",
                  borderTop: "1px solid rgba(255,215,0,0.2)",
                  paddingTop: "10px",
                }}
              >
                {ame.lastActivity
                  ? new Date(ame.lastActivity).toLocaleString("es-ES")
                  : "Sin actividad"}
              </p>
            </div>
          </button>
        ))}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: "15px",
          marginTop: "30px",
        }}
      >
        <button
          onClick={() => alert("Crear nuevo AME - Próximamente")}
          style={{
            background: "linear-gradient(135deg, #DC143C, #FF1744)",
            color: "#F0F0F8",
            border: "none",
            padding: "15px 25px",
            fontSize: "16px",
            fontWeight: "bold",
            borderRadius: "8px",
            cursor: "pointer",
          }}
        >
          + Crear AME
        </button>
        <button
          onClick={() => (window.location.href = "/ame/evolution")}
          style={{
            background: "rgba(255,215,0,0.1)",
            border: "2px solid #FFD700",
            color: "#FFD700",
            padding: "15px 25px",
            fontSize: "16px",
            fontWeight: "bold",
            borderRadius: "8px",
            cursor: "pointer",
          }}
        >
          Evolución
        </button>
        <button
          onClick={() => alert("Comunidad - Próximamente")}
          style={{
            background: "rgba(220,20,60,0.1)",
            border: "2px solid #DC143C",
            color: "#F0F0F8",
            padding: "15px 25px",
            fontSize: "16px",
            fontWeight: "bold",
            borderRadius: "8px",
            cursor: "pointer",
          }}
        >
          Comunidad
        </button>
      </div>

      <div
        style={{
          marginTop: "16px",
          padding: "14px 20px",
          background: "rgba(40, 40, 80, 0.4)",
          border: "1px solid rgba(0, 200, 83, 0.4)",
          borderRadius: "10px",
        }}
      >
        <strong style={{ fontSize: "14px", display: "block", marginBottom: "8px" }}>
          Nota de voz → texto (STT local 100% offline, en la PC)
        </strong>
        <button
          onClick={handleVoiceToggle}
          disabled={voiceInput.state === "transcribing"}
          style={{
            width: "100%",
            background: "rgba(124,77,255,0.15)",
            border: "2px solid #7c4dff",
            color: "#fff",
            padding: "10px",
            borderRadius: "8px",
            cursor: "pointer",
            fontSize: "14px",
            marginBottom: "8px",
          }}
        >
          {voiceInput.state === "recording"
            ? "⏹ Detener y transcribir"
            : voiceInput.state === "transcribing"
              ? "Transcribiendo…"
              : "🎙 Grabar nota de voz"}
        </button>
        <p style={{ color: "#aaa", fontSize: "12px", marginBottom: "6px" }}>{voiceStatusLabel}</p>
        {voiceText && (
          <p style={{ color: "#fff", fontSize: "13px", wordBreak: "break-word" }}>{voiceText}</p>
        )}
        {voiceError && <p style={{ color: "#DC143C", fontSize: "12px" }}>{voiceError}</p>}
      </div>
    </div>
  );
}
