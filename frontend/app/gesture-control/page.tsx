"use client";

import { useEffect, useRef, useState } from "react";
import { ParticleSystem3D } from "@/lib/particle-system";
import { JJK, glowColor } from "@/lib/jjk-theme";

type GestureResult = {
  gesture: string;
  confidence: number;
  fingers: number;
  landmarks?: number[][];
  center?: number[];
  error?: string;
};

const GESTURE_EMOJI: Record<string, string> = {
  fist: "✊",
  index: "☝️",
  peace: "✌️",
  open_hand: "✋",
  heart: "❤️",
  swipe: "👋",
  rock: "🤘",
  ok: "👌",
  none: "❓",
};

export default function GestureControlPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesCanvasRef = useRef<HTMLCanvasElement>(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [gesture, setGesture] = useState<GestureResult | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [domainExpansion, setDomainExpansion] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const particleSystem = useRef<ParticleSystem3D | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (particlesCanvasRef.current) {
      particleSystem.current = new ParticleSystem3D(particlesCanvasRef.current);
    }
    let lastFrame = performance.now();
    const loop = () => {
      const now = performance.now();
      const dt = Math.min(0.05, (now - lastFrame) / 1000);
      lastFrame = now;
      particleSystem.current?.update(dt);
      requestAnimationFrame(loop);
    };
    loop();
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const toggleCamera = async () => {
    if (cameraOn) {
      setCameraOn(false);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 },
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraOn(true);
      intervalRef.current = setInterval(() => sendFrame(), 100);
    } catch (err) {
      setApiError("Error accediendo a cámara: " + String(err));
    }
  };

  const sendFrame = async () => {
    if (!videoRef.current || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(videoRef.current, 0, 0, 320, 240);
    const base64 = canvas.toDataURL("image/jpeg").split(",")[1];
    try {
      const res = await fetch("/api/gesture/detect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_base64: base64 }),
      });
      const data: GestureResult = await res.json();
      setGesture(data);
      if (data.gesture && data.gesture !== "none" && particleSystem.current) {
        particleSystem.current.spawnFromGesture(
          data.gesture,
          data.center?.[0] || 0,
          data.center?.[1] || 0,
          data.center?.[2] || 0,
          data.confidence || 0.5,
        );
        setHistory((prev) => [data.gesture!, ...prev].slice(0, 10));
      }
    } catch (err) {
      setApiError("Error enviando frame: " + String(err));
    }
  };

  const toggleDomainExpansion = async () => {
    const next = !domainExpansion;
    setDomainExpansion(next);
    particleSystem.current?.setDomainExpansion(next);
    try {
      await fetch("/api/gesture/domain-expansion", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: next }),
      });
    } catch (err) {
      setApiError("Error en domain expansion: " + String(err));
    }
  };

  return (
    <div
      style={{
        backgroundColor: JJK.BG,
        color: JJK.TEXT,
        minHeight: "100vh",
        fontFamily: "'JetBrains Mono', 'Courier New', monospace",
      }}
    >
      <header style={{ maxWidth: 1200, margin: "0 auto", padding: "20px" }}>
        <h1 style={{ textShadow: `0 0 20px ${glowColor(JJK.ACCENT, 0.7)}`, textAlign: "center", fontSize: "2rem" }}>
          ⚡ AURA Gesture Control ⚡
        </h1>
        <p style={{ textAlign: "center", color: JJK.ACCENT2, marginBottom: 20 }}>
          Control por gestos + partículas malditas
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", marginBottom: 20 }}>
          <button
            onClick={toggleCamera}
            style={{
              background: cameraOn ? JJK.RED : JJK.ACCENT,
              color: "#fff",
              border: "none",
              padding: "10px 20px",
              borderRadius: 8,
              cursor: "pointer",
              fontWeight: "bold",
            }}
          >
            {cameraOn ? "⏹ Detener cámara" : "🎥 Activar cámara"}
          </button>
          <button
            onClick={toggleDomainExpansion}
            style={{
              background: domainExpansion ? "transparent" : JJK.CURSED_ENERGY,
              color: "#fff",
              border: `2px solid ${JJK.CURSED_ENERGY}`,
              padding: "10px 20px",
              borderRadius: 8,
              cursor: "pointer",
              fontWeight: "bold",
              boxShadow: domainExpansion ? `0 0 30px ${glowColor(JJK.CURSED_ENERGY, 0.8)}` : "none",
            }}
          >
            {domainExpansion ? "🌀 Desactivar Domain Expansion" : "🌐 Domain Expansion"}
          </button>
        </div>
        {apiError && (
          <p style={{ color: JJK.RED, textAlign: "center", marginBottom: 10 }}>{apiError}</p>
        )}
      </header>

      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "0 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <section
          style={{
            backgroundColor: JJK.PANEL,
            border: `1px solid ${JJK.ACCENT}44`,
            borderRadius: 12,
            padding: 20,
            boxShadow: `0 0 20px ${glowColor(JJK.ACCENT, 0.15)}`,
            minHeight: 400,
          }}
        >
          <h2 style={{ marginBottom: 10, color: JJK.ACCENT2 }}>🎥 Cámara</h2>
          <video ref={videoRef} style={{ width: "100%", borderRadius: 8, display: cameraOn ? "block" : "none" }} />
          <canvas ref={canvasRef} width={320} height={240} style={{ display: "none" }} />
          {!cameraOn && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, color: "#555" }}>
              Cámara apagada
            </div>
          )}
          {gesture && gesture.gesture !== "none" && (
            <div
              style={{
                marginTop: 15,
                padding: 15,
                border: `1px solid ${JJK.ACCENT2}55`,
                borderRadius: 8,
                textAlign: "center",
                background: "rgba(0,0,0,0.5)",
              }}
            >
              <div style={{ fontSize: "3rem" }}>{GESTURE_EMOJI[gesture.gesture] || "❓"}</div>
              <div style={{ fontSize: "1.3rem", fontWeight: "bold", color: JJK.ACCENT2 }}>
                {gesture.gesture}
              </div>
              <div style={{ color: "#aaa" }}>
                Confianza: {(gesture.confidence * 100).toFixed(1)}% | Dedos: {gesture.fingers}
              </div>
            </div>
          )}
        </section>

        <section
          style={{
            backgroundColor: JJK.PANEL,
            border: `1px solid ${JJK.CURSED_ENERGY}44`,
            borderRadius: 12,
            padding: 20,
            boxShadow: `0 0 20px ${glowColor(JJK.CURSED_ENERGY, 0.15)}`,
            minHeight: 400,
            position: "relative",
          }}
        >
          <h2 style={{ marginBottom: 10, color: JJK.CURSED_ENERGY }}>✨ Partículas 3D</h2>
          <canvas ref={particlesCanvasRef} style={{ width: "100%", height: 300, borderRadius: 8, background: "rgba(0,0,0,0.3)" }} />
        </section>
      </main>

      <section
        style={{
          maxWidth: 1200,
          margin: "20px auto",
          padding: "0 20px",
        }}
      >
        <div
          style={{
            backgroundColor: JJK.PANEL,
            border: `1px solid ${JJK.ACCENT}33`,
            borderRadius: 12,
            padding: 20,
          }}
        >
          <h2 style={{ color: JJK.ACCENT, marginBottom: 10 }}>📜 Historial de gestos</h2>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {history.map((g, i) => (
              <span
                key={i}
                style={{
                  padding: "4px 12px",
                  background: `${JJK.ACCENT}22`,
                  border: `1px solid ${JJK.ACCENT}55`,
                  borderRadius: 20,
                  fontSize: "0.9rem",
                }}
              >
                {GESTURE_EMOJI[g] || "❓"} {g}
              </span>
            ))}
            {history.length === 0 && (
              <span style={{ color: "#555" }}>Sin gestos detectados aún</span>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}