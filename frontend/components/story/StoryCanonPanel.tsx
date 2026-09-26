"use client";

/**
 * Vista de canon, continuidad, cronología y conflictos.
 * Contrato real:
 * - GET  /api/story/{work_id}/canon | /continuity | /chronology | /conflicts
 * - POST /api/story/{work_id}/canon | /continuity  {description,timestamp,scene_ref,source}
 */

import { useCallback, useEffect, useState } from "react";
import { JJK } from "@/lib/jjk-theme";
import { formatEventTime } from "@/lib/story-format";
import {
  addEvent,
  getChronology,
  getConflicts,
  listEvents,
  StoryApiError,
} from "@/lib/story-client";
import type { StoryConflict, StoryEvent } from "@/lib/story-types";

interface Props {
  workId: string;
}

export default function StoryCanonPanel({ workId }: Props) {
  const [events, setEvents] = useState<StoryEvent[]>([]);
  const [conflicts, setConflicts] = useState<StoryConflict[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState<"canon" | "continuity">("canon");

  const refresh = useCallback(async () => {
    if (!workId) return;
    setLoading(true);
    setError(null);
    try {
      const [chron, conf] = await Promise.all([
        getChronology(workId, 100),
        getConflicts(workId),
      ]);
      setEvents(chron.events || []);
      setConflicts(conf.conflicts || []);
    } catch (err: unknown) {
      setError(
        err instanceof StoryApiError ? err.message : "Error al cargar canon"
      );
    } finally {
      setLoading(false);
    }
  }, [workId]);

  useEffect(() => {
    setEvents([]);
    setConflicts([]);
    void refresh();
  }, [workId, refresh]);

  const handleAdd = async () => {
    if (!description.trim() || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await addEvent(workId, kind, {
        description: description.trim(),
        timestamp: Date.now() / 1000,
        scene_ref: "",
        source: "user",
      });
      setNotice(`Evento ${kind === "canon" ? "canónico" : "de continuidad"} añadido.`);
      setDescription("");
      await refresh();
    } catch (err: unknown) {
      setError(
        err instanceof StoryApiError ? err.message : "Error al añadir evento"
      );
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
    <div className="space-y-4">
      <div
        className="rounded-lg p-4 border space-y-2"
        style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
      >
        <h3 className="font-bold" style={{ color: JJK.TEXT }}>
          ⚡ Añadir evento
        </h3>
        <div className="flex gap-2">
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as "canon" | "continuity")}
            className="p-2 rounded border text-sm"
            style={inputStyle}
          >
            <option value="canon">Canon (hecho oficial)</option>
            <option value="continuity">Continuidad (derivado)</option>
          </select>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Descripción del evento *"
            className="flex-1 p-2 rounded border text-sm"
            style={inputStyle}
          />
          <button
            onClick={handleAdd}
            disabled={busy || !description.trim()}
            className="px-4 rounded text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: JJK.ACCENT }}
          >
            {busy ? "…" : "Añadir"}
          </button>
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

      <div
        className="rounded-lg p-4 border"
        style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
      >
        <h3 className="font-bold mb-2" style={{ color: JJK.TEXT }}>
          🕰 Cronología ({events.length})
        </h3>
        {loading ? (
          <p className="text-sm" style={{ color: JJK.TEXT }}>
            Cargando…
          </p>
        ) : events.length === 0 ? (
          <p className="text-sm" style={{ color: `${JJK.TEXT}99` }}>
            Sin eventos aún.
          </p>
        ) : (
          <ol className="space-y-2 border-l-2 pl-4" style={{ borderColor: `${JJK.ACCENT}44` }}>
            {events.map((ev) => (
              <li key={ev.event_id} className="text-sm relative">
                <span
                  className="absolute -left-[21px] top-1.5 w-2.5 h-2.5 rounded-full"
                  style={{
                    background: ev.certainty === "canon" ? JJK.ACCENT : JJK.ACCENT2,
                  }}
                />
                <span style={{ color: JJK.TEXT }}>{ev.description}</span>
                <span className="ml-2 text-xs" style={{ color: `${JJK.TEXT}66` }}>
                  {formatEventTime(ev.timestamp)} · {ev.certainty}
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>

      <div
        className="rounded-lg p-4 border"
        style={{
          borderColor: conflicts.length > 0 ? `${JJK.RED}66` : `${JJK.ACCENT}33`,
          background: JJK.PANEL,
        }}
      >
        <h3 className="font-bold mb-2" style={{ color: JJK.TEXT }}>
          {conflicts.length > 0 ? "🚨" : "✅"} Coherencia del canon (
          {conflicts.length} conflictos)
        </h3>
        {conflicts.length === 0 ? (
          <p className="text-sm" style={{ color: `${JJK.TEXT}99` }}>
            Sin contradicciones detectadas en el canon.
          </p>
        ) : (
          <ul className="space-y-2">
            {conflicts.map((c, i) => (
              <li
                key={i}
                className="text-sm p-2 rounded"
                style={{ background: `${JJK.RED}15`, color: JJK.RED }}
              >
                {JSON.stringify(c)}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
