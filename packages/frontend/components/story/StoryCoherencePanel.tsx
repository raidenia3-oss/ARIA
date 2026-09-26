"use client";

/**
 * Panel de coherencia — valida un texto contra la Character Bible y el canon.
 * Contrato real:
 * - POST /api/story/{work_id}/check-consistency {char_id, text} → FullConsistencyResult
 */

import { useEffect, useState } from "react";
import { JJK } from "@/lib/jjk-theme";
import { checkConsistency, listCharacters, StoryApiError } from "@/lib/story-client";
import type { FullConsistencyResult, StoryCharacter } from "@/lib/story-types";

interface Props {
  workId: string;
  initialText?: string;
}

export default function StoryCoherencePanel({ workId, initialText }: Props) {
  const [characters, setCharacters] = useState<StoryCharacter[]>([]);
  const [charId, setCharId] = useState("");
  const [text, setText] = useState(initialText || "");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FullConsistencyResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCharacters([]);
    setCharId("");
    listCharacters(workId)
      .then((res) => {
        if (cancelled) return;
        setCharacters(res.characters || []);
        if (res.characters?.length > 0) setCharId(res.characters[0].char_id);
      })
      .catch(() => {
        if (!cancelled) setError("No se pudieron cargar los personajes");
      });
    return () => {
      cancelled = true;
    };
  }, [workId]);

  useEffect(() => {
    if (initialText !== undefined) setText(initialText);
  }, [initialText]);

  useEffect(() => {
    if (characters.length > 0 && !charId) setCharId(characters[0].char_id);
  }, [characters, charId]);

  const runCheck = async () => {
    if (!charId || !text.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await checkConsistency(workId, charId, text.trim());
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error al validar coherencia");
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = {
    background: JJK.BG,
    color: JJK.TEXT,
    borderColor: `${JJK.ACCENT}33`,
  };

  return (
    <div
      className="rounded-lg p-4 border space-y-3"
      style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
    >
      <h3 className="font-bold" style={{ color: JJK.TEXT }}>
        🧩 Panel de coherencia
      </h3>

      {characters.length === 0 ? (
        <p className="text-sm" style={{ color: `${JJK.TEXT}99` }}>
          Crea primero un personaje para poder validar coherencia.
        </p>
      ) : (
        <>
          <select
            value={charId}
            onChange={(e) => setCharId(e.target.value)}
            className="w-full p-2 rounded border text-sm"
            style={inputStyle}
          >
            {characters.map((c) => (
              <option key={c.char_id} value={c.char_id}>
                {c.name} ({c.char_id})
              </option>
            ))}
          </select>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Pega aquí el texto o diálogo a validar…"
            rows={5}
            className="w-full p-2 rounded border text-sm"
            style={inputStyle}
          />
          <button
            onClick={runCheck}
            disabled={loading || !text.trim()}
            className="py-2 px-4 rounded text-white font-semibold text-sm disabled:opacity-50"
            style={{ background: JJK.ACCENT }}
          >
            {loading ? "Validando…" : "Validar coherencia"}
          </button>
        </>
      )}

      {error && (
        <p className="text-sm" style={{ color: JJK.RED }}>
          ⚠ {error}
        </p>
      )}

      {result && (
        <div
          className="rounded p-3 space-y-2 text-sm"
          style={{
            background: result.overall_pass ? `${JJK.ACCENT2}11` : `${JJK.RED}15`,
            border: `1px solid ${result.overall_pass ? `${JJK.ACCENT2}55` : `${JJK.RED}66`}`,
          }}
        >
          <p
            className="font-bold"
            style={{ color: result.overall_pass ? JJK.ACCENT2 : JJK.RED }}
          >
            {result.overall_pass
              ? "✅ El texto es coherente con el canon y el personaje."
              : "🚨 Problemas de coherencia detectados:"}
          </p>

          {result.character_consistency.violations?.length > 0 && (
            <ul style={{ color: JJK.RED }}>
              {result.character_consistency.violations.map((v, i) => (
                <li key={i}>
                  • [{v.type}] {v.description}
                </li>
              ))}
            </ul>
          )}

          {result.canon_consistency.contradictions?.length > 0 && (
            <ul style={{ color: JJK.RED }}>
              {result.canon_consistency.contradictions.map((c, i) => (
                <li key={i}>
                  • Contradicción canónica: {c.message} (evento: {c.description})
                </li>
              ))}
            </ul>
          )}

          <p style={{ color: `${JJK.TEXT}88` }}>
            Clasificación de fuente:{" "}
            <strong style={{ color: JJK.TEXT }}>
              {result.source_classification.classification}
            </strong>
            {result.source_classification.reason
              ? ` (${result.source_classification.reason})`
              : ""}
          </p>

          {result.character_consistency.checks?.length > 0 && (
            <ul className="text-xs" style={{ color: `${JJK.TEXT}77` }}>
              {result.character_consistency.checks.map((ck, i) => (
                <li key={i}>
                  {ck.result === "pass" ? "✓" : ck.result === "warn" ? "△" : "✗"}{" "}
                  {ck.name}
                  {ck.characteristic ? ` — ${ck.characteristic}` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
