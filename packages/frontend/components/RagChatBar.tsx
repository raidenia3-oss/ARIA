"use client";

import { useEffect, useRef, useState } from "react";
import { RagQueryResponse } from "@/types/nomad";

const BACKEND_BASE =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") || "http://127.0.0.1:8008";

interface Props {
  onInsert: (text: string, sources: RagQueryResponse["sources"]) => void;
}

export default function RagChatBar({ onInsert }: Props) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RagQueryResponse | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleQuery = async () => {
    const value = query.trim();
    if (!value || loading) return;

    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${BACKEND_BASE}/api/nomad/rag/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: value, limit: 5 }),
      });

      if (!res.ok) {
        const err = await res.text();
        throw new Error(err || `Error ${res.status}`);
      }

      const data = (await res.json()) as RagQueryResponse;
      setResult(data);
      onInsert(data.context || value, data.sources);
      setQuery("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error desconocido";
      onInsert(`[RAG ERROR] ${msg}`, []);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        borderTop: "1px solid rgba(0,240,255,0.18)",
        background: "rgba(5,10,15,0.85)",
        padding: 10,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", gap: 8 }}>
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Consulta RAG N.O.M.A.D..."
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              handleQuery();
            }
          }}
          style={{
            flex: 1,
            background: "rgba(0,0,0,0.35)",
            color: "#e0f7ff",
            border: "1px solid rgba(0,240,255,0.3)",
            borderRadius: 4,
            padding: "8px 10px",
            fontSize: 12,
            outline: "none",
          }}
        />
        <button
          type="button"
          onClick={handleQuery}
          disabled={loading}
          style={{
            background: loading ? "rgba(0,240,255,0.15)" : "rgba(0,240,255,0.25)",
            color: "#00f0ff",
            border: "1px solid rgba(0,240,255,0.5)",
            borderRadius: 4,
            padding: "8px 12px",
            fontWeight: 700,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "..." : "RAG"}
        </button>
      </div>

      {result && result.sources.length > 0 && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 6,
            maxHeight: 120,
            overflowY: "auto",
          }}
        >
          {result.sources.map((src, idx) => (
            <span
              key={idx}
              title={`score: ${src.score.toFixed(2)}`}
              style={{
                fontSize: 10,
                color: "#9ad7ff",
                background: "rgba(0,240,255,0.08)",
                border: "1px solid rgba(0,240,255,0.18)",
                borderRadius: 999,
                padding: "4px 8px",
              }}
            >
              FUENTE {idx + 1}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
