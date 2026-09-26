"use client";

/**
 * Vinculación de una sesión de chat con obra + personaje.
 * Contrato real:
 * - GET    /api/story/sessions/{session_id}/context → {status:"active"|"no_context",...}
 * - POST   /api/story/sessions/{session_id}/context {work_id, character_id}
 * - DELETE /api/story/sessions/{session_id}/context → {cleared:true}
 *
 * El session_id se guarda en localStorage ("aura-chat-session-id") y el chat
 * lo envía opcionalmente a /api/chat — sin cambiar su contrato.
 */

import { useEffect, useState } from "react";
import { JJK } from "@/lib/jjk-theme";
import {
  bindSession,
  getSessionContext,
  listCharacters,
  StoryApiError,
  unbindSession,
} from "@/lib/story-client";
import type { StoryCharacter } from "@/lib/story-types";

interface Props {
  workId: string;
}

const SESSION_KEY = "aura-chat-session-id";

export default function StorySessionLink({ workId }: Props) {
  const [characters, setCharacters] = useState<StoryCharacter[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [charId, setCharId] = useState("");
  const [active, setActive] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem(SESSION_KEY);
    if (saved) setSessionId(saved);
  }, []);

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

  const checkContext = async () => {
    if (!sessionId.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await getSessionContext(sessionId.trim());
      setActive(res.active);
      setNotice(
        res.active
          ? `Sesión vinculada a obra "${res.context?.work_id}" / personaje "${res.context?.character_id}".`
          : "La sesión no tiene contexto literario activo."
      );
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error al consultar");
    } finally {
      setBusy(false);
    }
  };

  const handleBind = async () => {
    if (!sessionId.trim() || !charId || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await bindSession(sessionId.trim(), { work_id: workId, character_id: charId });
      localStorage.setItem(SESSION_KEY, sessionId.trim());
      setActive(true);
      setNotice(
        `Sesión "${sessionId.trim()}" vinculada a "${workId}" / "${charId}". El chat usará este contexto.`
      );
    } catch (err: unknown) {
      setError(
        err instanceof StoryApiError ? err.message : "Error al vincular sesión"
      );
    } finally {
      setBusy(false);
    }
  };

  const handleUnbind = async () => {
    if (!sessionId.trim() || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await unbindSession(sessionId.trim());
      setActive(false);
      setNotice("Sesión desvinculada.");
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error al desvincular");
    } finally {
      setBusy(false);
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
        🔗 Vincular chat con la obra
      </h3>
      <p className="text-xs" style={{ color: `${JJK.TEXT}77` }}>
        El chat existente envía <code>session_id</code> opcionalmente; si está
        vinculado, el backend inyecta el contexto literario (biblia, canon y
        plan) sin cambiar el contrato del chat.
      </p>
      <input
        value={sessionId}
        onChange={(e) => setSessionId(e.target.value)}
        placeholder="ID de sesión de chat"
        className="w-full p-2 rounded border text-sm"
        style={inputStyle}
      />
      <select
        value={charId}
        onChange={(e) => setCharId(e.target.value)}
        className="w-full p-2 rounded border text-sm"
        style={inputStyle}
      >
        {characters.length === 0 ? (
          <option value="">— sin personajes —</option>
        ) : (
          characters.map((c) => (
            <option key={c.char_id} value={c.char_id}>
              {c.name} ({c.char_id})
            </option>
          ))
        )}
      </select>
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={handleBind}
          disabled={busy || !sessionId.trim() || !charId}
          className="py-2 px-4 rounded text-white font-semibold text-sm disabled:opacity-50"
          style={{ background: JJK.ACCENT }}
        >
          {busy ? "…" : "Vincular"}
        </button>
        <button
          onClick={handleUnbind}
          disabled={busy || !sessionId.trim()}
          className="py-2 px-4 rounded text-sm disabled:opacity-50"
          style={{ border: `1px solid ${JJK.ACCENT}55`, color: JJK.TEXT }}
        >
          Desvincular
        </button>
        <button
          onClick={checkContext}
          disabled={busy || !sessionId.trim()}
          className="py-2 px-4 rounded text-sm disabled:opacity-50"
          style={{ border: `1px solid ${JJK.ACCENT}55`, color: JJK.TEXT }}
        >
          Consultar estado
        </button>
      </div>
      {active !== null && (
        <p className="text-xs" style={{ color: `${JJK.TEXT}77` }}>
          Estado: {active ? "🟢 activa" : "⚪ sin contexto"}
        </p>
      )}
      {notice && (
        <p className="text-xs" style={{ color: JJK.ACCENT2 }}>
          {notice}
        </p>
      )}
      {error && (
        <p className="text-xs" style={{ color: JJK.RED }}>
          ⚠ {error}
        </p>
      )}
    </div>
  );
}
