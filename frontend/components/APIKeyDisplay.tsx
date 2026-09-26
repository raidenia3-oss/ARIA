"use client";

import { useState } from "react";
import { palette, withHover } from "./palette";

function generateKey(): string {
  const rand = Array.from(crypto.getRandomValues(new Uint8Array(24)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return `ame_sk_${rand}`;
}

export default function APIKeyDisplay({
  initialKey,
}: {
  initialKey?: string;
}) {
  const [key, setKey] = useState(initialKey || generateKey());
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(key);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = key;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const regenerate = () => {
    setKey(generateKey());
    setCopied(false);
  };

  const baseCode: React.CSSProperties = {
    flex: 1,
    color: palette.accent,
    fontSize: "12px",
    wordBreak: "break-all",
  };

  const copyBtn = withHover(
    {
      background: palette.accent,
      color: palette.bg,
      border: "none",
      padding: "8px 16px",
      borderRadius: "4px",
      cursor: "pointer",
      fontWeight: 700,
    },
    { opacity: 0.85 },
  );

  const regenBtn = withHover(
    {
      background: "transparent",
      color: palette.accent,
      border: `1px solid ${palette.accent}`,
      padding: "8px 16px",
      borderRadius: "4px",
      cursor: "pointer",
      fontWeight: 700,
    },
    { background: "rgba(255,215,0,0.1)" },
  );

  return (
    <div
      style={{
        background: palette.cardBg,
        border: `2px solid ${palette.accent}`,
        borderRadius: "12px",
        padding: "25px",
        marginBottom: "30px",
      }}
    >
      <h2 style={{ margin: "0 0 8px 0" }}>🔐 Tu API Personal</h2>
      <p style={{ margin: "0 0 20px 0", opacity: 0.7, fontSize: "14px" }}>
        Usa esta llave para autenticar peticiones a la API de AME y
        webhooks personalizados.
      </p>

      <div
        style={{
          background: palette.bg,
          padding: "15px",
          borderRadius: "6px",
          marginBottom: "15px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
          flexWrap: "wrap",
        }}
      >
        <code style={baseCode}>{key}</code>
        <button {...copyBtn} onClick={copy}>
          {copied ? "✅ Copiado" : "📋 Copiar"}
        </button>
      </div>

      <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
        <button {...regenBtn} onClick={regenerate}>
          🔄 Regenerar Key
        </button>
        <a
          href="/docs/webhooks"
          style={{
            color: palette.accent,
            textDecoration: "none",
            fontWeight: 700,
            border: `1px solid ${palette.accent}`,
            padding: "8px 16px",
            borderRadius: "4px",
          }}
        >
          📚 Documentación →
        </a>
      </div>
    </div>
  );
}
