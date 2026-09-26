"use client";

import { useState, useEffect } from "react";
import SecurityLockScreen from "./SecurityLockScreen";

export default function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("aura_authenticated");
      if (stored === "true") {
        setIsAuthenticated(true);
      }
    } catch {
      // localStorage unavailable
    }
    setIsReady(true);
  }, []);

  const unlock = () => setIsAuthenticated(true);

  const lock = () => {
    try {
      localStorage.removeItem("aura_authenticated");
    } catch {
      // localStorage unavailable
    }
    setIsAuthenticated(false);
  };

  if (!isReady) {
    return (
      <div
        style={{
          position: "fixed",
          inset: 0,
          background: "#050a0f",
          zIndex: 9999,
        }}
      />
    );
  }

  if (!isAuthenticated) {
    return <SecurityLockScreen onUnlock={unlock} />;
  }

  return (
    <>
      <header
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 100,
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          padding: "12px 20px",
          background: "linear-gradient(to bottom, rgba(5,10,15,0.95), rgba(5,10,15,0))",
          pointerEvents: "none",
        }}
      >
        <button
          onClick={lock}
          style={{
            pointerEvents: "auto",
            background: "rgba(255,42,109,0.1)",
            border: "1px solid rgba(255,42,109,0.4)",
            color: "#ff2a6d",
            padding: "8px 16px",
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: 2,
            textTransform: "uppercase",
            cursor: "pointer",
            borderRadius: 2,
            fontFamily:
              'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, monospace',
            transition: "all 0.2s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(255,42,109,0.25)";
            e.currentTarget.style.boxShadow = "0 0 15px rgba(255,42,109,0.3)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "rgba(255,42,109,0.1)";
            e.currentTarget.style.boxShadow = "none";
          }}
        >
          Lock System
        </button>
      </header>
      <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
    </>
  );
}
