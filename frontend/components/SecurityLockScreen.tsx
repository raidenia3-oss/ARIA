"use client";

import { useState, useEffect, useCallback } from "react";

const CYAN = "#00f0ff";
const OBSIDIAN = "#050a0f";
const DARK_CARD = "#0a1118";
const ERROR_RED = "#ff2a6d";

export default function SecurityLockScreen({
  onUnlock,
}: {
  onUnlock: () => void;
}) {
  const [key, setKey] = useState("");
  const [error, setError] = useState(false);
  const [time, setTime] = useState("");

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(
        now.toLocaleTimeString("es-ES", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      );
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);

  const handleUnlock = useCallback(() => {
    const expected =
      typeof process !== "undefined"
        ? process.env.NEXT_PUBLIC_AURA_KEY
        : undefined;

    if (!expected || key !== expected) {
      setError(true);
      setTimeout(() => setError(false), 1200);
      return;
    }

    try {
      localStorage.setItem("aura_authenticated", "true");
    } catch {
      // localStorage unavailable
    }
    onUnlock();
  }, [key, onUnlock]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleUnlock();
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: OBSIDIAN,
        color: "#e0f7ff",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        overflow: "hidden",
        fontFamily:
          'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, monospace',
      }}
    >
      <style>{`
        @keyframes scanline {
          0% { transform: translateY(-100%); }
          100% { transform: translateY(100vh); }
        }
        @keyframes flicker {
          0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% {
            opacity: 1;
          }
          20%, 24%, 55% {
            opacity: 0.4;
          }
        }
        @keyframes pulse-glow {
          0%, 100% { box-shadow: 0 0 15px rgba(0,240,255,0.3), inset 0 0 15px rgba(0,240,255,0.1); }
          50% { box-shadow: 0 0 30px rgba(0,240,255,0.6), inset 0 0 25px rgba(0,240,255,0.2); }
        }
        .scanline-overlay {
          position: absolute;
          inset: 0;
          background: linear-gradient(
            to bottom,
            transparent 50%,
            rgba(0, 240, 255, 0.03) 50%
          );
          background-size: 100% 4px;
          pointer-events: none;
          z-index: 2;
        }
        .scan-beam {
          position: absolute;
          left: 0;
          right: 0;
          height: 120px;
          background: linear-gradient(
            to bottom,
            transparent,
            rgba(0, 240, 255, 0.08),
            transparent
          );
          animation: scanline 4s linear infinite;
          pointer-events: none;
          z-index: 3;
        }
        .grid-bg {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(0,240,255,0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,240,255,0.04) 1px, transparent 1px);
          background-size: 60px 60px;
          pointer-events: none;
        }
        .lock-card {
          position: relative;
          z-index: 4;
          background: ${DARK_CARD};
          border: 1px solid rgba(0,240,255,0.25);
          padding: 40px 32px;
          border-radius: 4px;
          min-width: 360px;
          max-width: 90vw;
          animation: pulse-glow 3s ease-in-out infinite, flicker 6s linear infinite;
        }
        .lock-input {
          width: 100%;
          padding: 14px 16px;
          background: rgba(5,10,15,0.8);
          border: 1px solid rgba(0,240,255,0.3);
          color: ${CYAN};
          font-family: inherit;
          font-size: 16px;
          letter-spacing: 2px;
          border-radius: 2px;
          outline: none;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .lock-input:focus {
          border-color: ${CYAN};
          box-shadow: 0 0 12px rgba(0,240,255,0.25);
        }
        .lock-input.error {
          border-color: ${ERROR_RED};
          box-shadow: 0 0 12px rgba(255,42,109,0.35);
          animation: shake 0.4s ease-in-out;
        }
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-6px); }
          75% { transform: translateX(6px); }
        }
        .lock-btn {
          width: 100%;
          padding: 14px;
          background: linear-gradient(135deg, rgba(0,240,255,0.15), rgba(0,240,255,0.05));
          border: 1px solid ${CYAN};
          color: ${CYAN};
          font-family: inherit;
          font-size: 14px;
          font-weight: 700;
          letter-spacing: 3px;
          text-transform: uppercase;
          cursor: pointer;
          border-radius: 2px;
          transition: all 0.2s;
          margin-top: 16px;
        }
        .lock-btn:hover {
          background: linear-gradient(135deg, rgba(0,240,255,0.3), rgba(0,240,255,0.1));
          box-shadow: 0 0 20px rgba(0,240,255,0.3);
        }
        .lock-btn:active {
          transform: scale(0.98);
        }
        .error-msg {
          color: ${ERROR_RED};
          font-size: 12px;
          letter-spacing: 1px;
          margin-top: 10px;
          min-height: 18px;
          text-transform: uppercase;
        }
      `}</style>

      <div className="grid-bg" />
      <div className="scanline-overlay" />
      <div className="scan-beam" />

      <div className="lock-card">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 24,
            borderBottom: "1px solid rgba(0,240,255,0.15)",
            paddingBottom: 16,
          }}
        >
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: CYAN,
              boxShadow: `0 0 10px ${CYAN}`,
            }}
          />
          <span
            style={{
              fontSize: 11,
              letterSpacing: 4,
              textTransform: "uppercase",
              opacity: 0.8,
            }}
          >
            AURA Security Protocol v4.0
          </span>
        </div>

        <h1
          style={{
            margin: "0 0 8px 0",
            fontSize: 22,
            fontWeight: 700,
            letterSpacing: 2,
            color: CYAN,
            textShadow: `0 0 10px rgba(0,240,255,0.5)`,
          }}
        >
          AURA SECURITY KEY
        </h1>
        <p
          style={{
            margin: "0 0 24px 0",
            fontSize: 12,
            opacity: 0.6,
            letterSpacing: 1,
          }}
        >
          Ingresa la clave de acceso para desbloquear el sistema
        </p>

        <input
          className={`lock-input${error ? " error" : ""}`}
          type="password"
          placeholder="&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;&#9679;"
          value={key}
          onChange={(e) => {
            setKey(e.target.value);
            if (error) setError(false);
          }}
          onKeyDown={handleKeyDown}
        />

        <button className="lock-btn" onClick={handleUnlock}>
          Desbloquear
        </button>

        <div className="error-msg">
          {error ? "Clave invalida — acceso denegado" : ""}
        </div>

        <div
          style={{
            marginTop: 20,
            paddingTop: 14,
            borderTop: "1px solid rgba(0,240,255,0.1)",
            display: "flex",
            justifyContent: "space-between",
            fontSize: 10,
            opacity: 0.5,
            letterSpacing: 1,
          }}
        >
          <span>SISTEMA BLOQUEADO</span>
          <span>{time}</span>
        </div>
      </div>
    </div>
  );
}
