"use client";

/**
 * Selector de obra/universo + creación y borrado de obras.
 * Contrato real: GET/POST /api/story/works, DELETE /api/story/works/{work_id}
 */

import { useState } from "react";
import { JJK } from "@/lib/jjk-theme";
import { slugify } from "@/lib/story-format";
import { createWork, deleteWork, StoryApiError } from "@/lib/story-client";
import type { StoryWork } from "@/lib/story-types";

interface Props {
  works: StoryWork[];
  selectedWorkId: string | null;
  loading: boolean;
  onSelect: (workId: string | null) => void;
  onWorksChanged: () => void;
}

export default function StoryWorkSelector({
  works,
  selectedWorkId,
  loading,
  onSelect,
  onWorksChanged,
}: Props) {
  const [title, setTitle] = useState("");
  const [universe, setUniverse] = useState("");
  const [description, setDescription] = useState("");
  const [author, setAuthor] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!title.trim() || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await createWork({
        work_id: slugify(title),
        title: title.trim(),
        universe: universe.trim(),
        description: description.trim(),
        author: author.trim(),
      });
      if (res.status === "exists") {
        setNotice(`La obra "${title.trim()}" ya existe.`);
      } else {
        setNotice(`Obra creada: ${title.trim()}`);
        onSelect(res.work_id);
      }
      setTitle("");
      setUniverse("");
      setDescription("");
      setAuthor("");
      onWorksChanged();
    } catch (err: unknown) {
      setError(
        err instanceof StoryApiError
          ? `No se pudo crear la obra: ${err.message}`
          : "Error desconocido al crear la obra"
      );
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (workId: string) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await deleteWork(workId);
      if (res.status === "cleared") {
        setNotice(`Obra "${workId}" eliminada.`);
        if (selectedWorkId === workId) onSelect(null);
        onWorksChanged();
      } else {
        setError(`No se pudo eliminar la obra (${res.status}).`);
      }
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error desconocido");
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
      <h2 className="font-bold" style={{ color: JJK.TEXT }}>
        📚 Obra / Universo
      </h2>

      {loading ? (
        <p style={{ color: JJK.TEXT }}>Cargando obras…</p>
      ) : works.length === 0 ? (
        <p style={{ color: `${JJK.TEXT}99` }}>Aún no hay obras. Crea la primera abajo.</p>
      ) : (
        <ul className="space-y-1">
          {works.map((w) => (
            <li key={w.work_id} className="flex items-center gap-2">
              <button
                onClick={() => onSelect(w.work_id)}
                className="flex-1 text-left px-3 py-2 rounded transition"
                style={{
                  background: selectedWorkId === w.work_id ? `${JJK.ACCENT}33` : "transparent",
                  border: `1px solid ${selectedWorkId === w.work_id ? JJK.ACCENT : `${JJK.ACCENT}22`}`,
                  color: JJK.TEXT,
                }}
              >
                <span className="font-semibold">{w.title}</span>
                {w.universe && (
                  <span style={{ color: `${JJK.TEXT}88` }}> · {w.universe}</span>
                )}
              </button>
              <button
                onClick={() => handleDelete(w.work_id)}
                disabled={busy}
                title={`Eliminar ${w.title}`}
                className="px-2 py-1 rounded text-xs disabled:opacity-40"
                style={{ border: `1px solid ${JJK.RED}55`, color: JJK.RED }}
              >
                🗑
              </button>
            </li>
          ))}
        </ul>
      )}

      <details>
        <summary className="cursor-pointer text-sm" style={{ color: JJK.ACCENT2 }}>
          ➕ Nueva obra
        </summary>
        <div className="mt-2 space-y-2">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Título de la obra *" className="w-full p-2 rounded border text-sm" style={inputStyle} />
          <input value={universe} onChange={(e) => setUniverse(e.target.value)} placeholder="Universo" className="w-full p-2 rounded border text-sm" style={inputStyle} />
          <input value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="Autor/a" className="w-full p-2 rounded border text-sm" style={inputStyle} />
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Descripción" rows={2} className="w-full p-2 rounded border text-sm" style={inputStyle} />
          <button
            onClick={handleCreate}
            disabled={busy || !title.trim()}
            className="w-full py-2 rounded text-white font-semibold text-sm disabled:opacity-50"
            style={{ background: JJK.ACCENT }}
          >
            {busy ? "Guardando…" : "Crear obra"}
          </button>
        </div>
      </details>

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
