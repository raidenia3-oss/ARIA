"use client";

/**
 * ChatIntegration — vincula una sesión de chat (session_id) con obra + personaje.
 *
 * Para /ame/[ameId]: el session_id es el propio ameId, porque
 * /api/mobile/chat ya envía session_id = ameId al backend. Al vincular
 * ameId → obra/personaje, el backend inyecta el contexto literario sin
 * cambiar NADA en el contrato del chat.
 *
 * Contrato real:
 * - GET    /api/story/sessions/{session_id}/context
 * - POST   /api/story/sessions/{session_id}/context {work_id, character_id}
 * - DELETE /api/story/sessions/{session_id}/context
 */

import { useEffect, useState } from "react";
import { JJK } from "@/lib/jjk-theme";
import {
  bindSession,
  getSessionContext,
  listCharacters,
  listWorks,
  StoryApiError,
  unbindSession,
} from "@/lib/story-client";
import type { StoryCharacter, StoryWork } from "@/lib/story-types";

interface Props {
  sessionId: string; // p.ej. ameId en /ame/[ameId]
  persistKey?: string; // si se indica, guarda el work_id elegido en localStorage
}

export default function ChatIntegration({ sessionId, persistKey }: Props) {
  const [works, setWorks] = useState<StoryWork[]>([]);
  const [characters, setCharacters] = useState<StoryCharacter[]>([]);
  const [workId, setWorkId] = useState("");
  const [charId, setCharId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [active, setActive] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    listWorks()
      .then((res) => {
        if (!cancelled) setWorks(res.works || []);
      })
      .catch(() => {
        if (!cancelled) setError("No se pudieron cargar las obras");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!workId) {
      setCharacters([]);
      setCharId("");
      return;
    }
    let cancelled = false;
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

  const handleBind = async () => {
    if (!workId || !charId || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await bindSession(sessionId, { work_id: workId, character_id: charId });
      setActive(true);
      setNotice("Contexto literario activo para este chat.");
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error al vincular");
    } finally {
      setBusy(false);
    }
  };

  const handleUnbind = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await unbindSession(sessionId);
      setActive(false);
      setNotice("Contexto literario desvinculado.");
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error al desvincular");
    } finally {
      setBusy(false);
    }
  };

  const checkContext = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await getSessionContext(sessionId);
      setActive(res.active);
      setNotice(res.active ? "Contexto activo." : "Sin contexto literario.");
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error al consultar");
    } finally {
      setBusy(false);
    }
  };

  const inputStyle = {
    background: JJK.BG,
    color: JJK.TEXT,
    borderColor: `${JJK.ACCENT}33`,
  };

  if (works.length === 0) {
    return null; // sin obras no se muestra nada sobre el chat
  }

  return (
    <div
      className="rounded-lg p-3 border space-y-2 text-sm"
      style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
    >
      <div className="flex gap-2 flex-wrap items-center">
        <select
          value={workId}
          onChange={(e) => setWorkId(e.target.value)}
          className="p-2 rounded border text-sm"
          style={inputStyle}
        >
          <option value="">— obra —</option>
          {works.map((w) => (
            <option key={w.work_id} value={w.work_id}>
              {w.title}
            </option>
          ))}
        </select>
        <select
          value={charId}
          onChange={(e) => setCharId(e.target.value)}
          disabled={characters.length === 0}
          className="p-2 rounded border text-sm"
          style={inputStyle}
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
        <button
          onClick={handleBind}
          disabled={busy || !workId || !charId}
          className="px-3 py-1.5 rounded text-white text-xs font-semibold disabled:opacity-50"
          style={{ background: JJK.ACCENT }}
        >
          {busy ? "…" : "Vincular"}
        </button>
        <button
          onClick={handleUnbind}
          disabled={busy}
          className="px-3 py-1.5 rounded text-xs disabled:opacity-50"
          style={{ border: `1px solid ${JJK.ACCENT}55`, color: JJK.TEXT }}
        >
          Desvincular
        </button>
        <button
          onClick={checkContext}
          disabled={busy}
          className="px-3 py-1.5 rounded text-xs disabled:opacity-50"
          style={{ border: `1px solid ${JJK.ACCENT}55`, color: JJK.TEXT }}
        >
          Estado
        </button>
        {active !== null && (
          <span className="text-xs" style={{ color: `${JJK.TEXT}77` }}>
            {active ? "🟢 activo" : "⚪ inactivo"}
          </span>
        )}
      </div>
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
