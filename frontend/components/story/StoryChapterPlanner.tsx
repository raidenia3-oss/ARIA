"use client";

/**
 * Planificador de capítulos y escenas.
 * Contrato real:
 * - GET  /api/story/{work_id}/chapters → {chapters, count, progress}
 * - POST /api/story/{work_id}/chapters {title,order,beat_summary}
 * - PUT  /api/story/{work_id}/chapters/{chapter_id} {status}
 * - POST /api/story/{work_id}/chapters/{chapter_id}/scenes {scene:{...}}
 */

import { useCallback, useEffect, useState } from "react";
import { JJK } from "@/lib/jjk-theme";
import { chapterStatusLabel } from "@/lib/story-format";
import {
  addScene,
  createChapter,
  listChapters,
  StoryApiError,
  updateChapterStatus,
} from "@/lib/story-client";
import { CHAPTER_STATUSES } from "@/lib/story-types";
import type { StoryChapter, StoryProgress } from "@/lib/story-types";

interface Props {
  workId: string;
}

export default function StoryChapterPlanner({ workId }: Props) {
  const [chapters, setChapters] = useState<StoryChapter[]>([]);
  const [progress, setProgress] = useState<StoryProgress | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [beat, setBeat] = useState("");
  const [sceneText, setSceneText] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    if (!workId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await listChapters(workId);
      setChapters(res.chapters || []);
      setProgress(res.progress || null);
    } catch (err: unknown) {
      setError(
        err instanceof StoryApiError ? err.message : "Error al cargar capítulos"
      );
    } finally {
      setLoading(false);
    }
  }, [workId]);

  useEffect(() => {
    setChapters([]);
    setProgress(null);
    void refresh();
  }, [workId, refresh]);

  const handleCreate = async () => {
    if (!title.trim() || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const nextOrder =
        chapters.length > 0 ? Math.max(...chapters.map((c) => c.order || 0)) + 1 : 1;
      const res = await createChapter(workId, {
        title: title.trim(),
        order: nextOrder,
        beat_summary: beat.trim(),
      });
      setNotice(`Capítulo "${res.chapter.title}" creado.`);
      setTitle("");
      setBeat("");
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error al crear capítulo");
    } finally {
      setBusy(false);
    }
  };

  const handleStatus = async (chapterId: string, status: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await updateChapterStatus(
        workId,
        chapterId,
        status as (typeof CHAPTER_STATUSES)[number]
      );
      if (res.error) {
        setError(`Backend rechazó el estado: ${res.error}`);
      } else {
        setNotice(`Estado actualizado a "${chapterStatusLabel(status)}".`);
        await refresh();
      }
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error al actualizar");
    } finally {
      setBusy(false);
    }
  };

  const handleScene = async (chapterId: string) => {
    const desc = (sceneText[chapterId] || "").trim();
    if (!desc || busy) return;
    setBusy(true);
    setError(null);
    try {
      await addScene(workId, chapterId, { title: desc, description: desc });
      setNotice(`Escena añadida al capítulo ${chapterId}.`);
      setSceneText((prev) => ({ ...prev, [chapterId]: "" }));
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error al añadir escena");
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
          🗺 Planificador
        </h3>
        {progress && (
          <p className="text-sm" style={{ color: `${JJK.TEXT}88` }}>
            {progress.total_chapters} capítulos · {progress.completed} completados (
            {progress.progress_percent}%) · {progress.in_progress} en progreso
          </p>
        )}
        <div className="flex gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Título del capítulo *"
            className="flex-1 p-2 rounded border text-sm"
            style={inputStyle}
          />
          <input
            value={beat}
            onChange={(e) => setBeat(e.target.value)}
            placeholder="Beat / resumen"
            className="flex-1 p-2 rounded border text-sm"
            style={inputStyle}
          />
          <button
            onClick={handleCreate}
            disabled={busy || !title.trim()}
            className="px-4 rounded text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: JJK.ACCENT }}
          >
            {busy ? "…" : "Crear"}
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

      {loading ? (
        <p className="text-sm" style={{ color: JJK.TEXT }}>
          Cargando capítulos…
        </p>
      ) : chapters.length === 0 ? (
        <p className="text-sm" style={{ color: `${JJK.TEXT}99` }}>
          Sin capítulos planificados.
        </p>
      ) : (
        <ul className="space-y-3">
          {[...chapters]
            .sort((a, b) => (a.order || 0) - (b.order || 0))
            .map((ch) => (
              <li
                key={ch.chapter_id}
                className="rounded-lg p-4 border"
                style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
              >
                <div className="flex justify-between items-center gap-2">
                  <div>
                    <span className="font-semibold" style={{ color: JJK.TEXT }}>
                      Cap. {ch.order}: {ch.title}
                    </span>
                    <span
                      className="ml-2 text-xs px-2 py-0.5 rounded"
                      style={{
                        background: `${JJK.ACCENT}22`,
                        color: JJK.ACCENT2,
                      }}
                    >
                      {chapterStatusLabel(ch.status)}
                    </span>
                  </div>
                  <select
                    value={ch.status}
                    onChange={(e) => handleStatus(ch.chapter_id, e.target.value)}
                    disabled={busy}
                    className="p-1 rounded border text-xs"
                    style={inputStyle}
                  >
                    {CHAPTER_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {chapterStatusLabel(s)}
                      </option>
                    ))}
                  </select>
                </div>
                {ch.beat_summary && (
                  <p className="text-sm mt-1" style={{ color: `${JJK.TEXT}88` }}>
                    {ch.beat_summary}
                  </p>
                )}
                {ch.scenes?.length > 0 && (
                  <ul className="text-xs mt-2 space-y-1" style={{ color: `${JJK.TEXT}77` }}>
                    {ch.scenes.map((sc) => (
                      <li key={sc.scene_id}>🎬 {sc.title || sc.description || sc.scene_id}</li>
                    ))}
                  </ul>
                )}
                <div className="flex gap-2 mt-2">
                  <input
                    value={sceneText[ch.chapter_id] || ""}
                    onChange={(e) =>
                      setSceneText((prev) => ({
                        ...prev,
                        [ch.chapter_id]: e.target.value,
                      }))
                    }
                    placeholder="Nueva escena…"
                    className="flex-1 p-2 rounded border text-sm"
                    style={inputStyle}
                  />
                  <button
                    onClick={() => handleScene(ch.chapter_id)}
                    disabled={busy || !(sceneText[ch.chapter_id] || "").trim()}
                    className="px-3 rounded text-xs text-white disabled:opacity-50"
                    style={{ background: `${JJK.ACCENT}cc` }}
                  >
                    + Escena
                  </button>
                </div>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
