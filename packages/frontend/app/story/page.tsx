"use client";

/**
 * Base Literaria AURA/AME — /story
 * Integra: selector de obra, personajes, canon/continuidad, cronología,
 * planificador de capítulos, panel de coherencia y vinculación de sesión.
 * Usa exclusivamente el contrato real /api/story (backend/story_routes.py).
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { JJK, glowColor } from "@/lib/jjk-theme";
import { listWorks, StoryApiError } from "@/lib/story-client";
import type { StoryWork } from "@/lib/story-types";
import StoryWorkSelector from "@/components/story/StoryWorkSelector";
import StoryCharacterEditor from "@/components/story/StoryCharacterEditor";
import StoryCanonPanel from "@/components/story/StoryCanonPanel";
import StoryChapterPlanner from "@/components/story/StoryChapterPlanner";
import StoryCoherencePanel from "@/components/story/StoryCoherencePanel";
import StorySessionLink from "@/components/story/StorySessionLink";

const WORK_KEY = "aura-story-work-id";

const TABS = [
  { id: "characters", label: "👤 Personajes" },
  { id: "canon", label: "⚡ Canon y cronología" },
  { id: "chapters", label: "🗺 Capítulos" },
  { id: "coherence", label: "🧩 Coherencia" },
  { id: "session", label: "🔗 Chat" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function StoryPage() {
  const [works, setWorks] = useState<StoryWork[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedWorkId, setSelectedWorkId] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("characters");

  const loadWorks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listWorks();
      setWorks(res.works || []);
    } catch (err: unknown) {
      setError(
        err instanceof StoryApiError
          ? `No se pudo conectar con la base literaria: ${err.message}`
          : "Error desconocido al cargar obras"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorks();
    const saved = localStorage.getItem(WORK_KEY);
    if (saved) setSelectedWorkId(saved);
  }, [loadWorks]);

  const handleSelect = (workId: string | null) => {
    setSelectedWorkId(workId);
    if (workId) localStorage.setItem(WORK_KEY, workId);
    else localStorage.removeItem(WORK_KEY);
  };

  const selectedWork = works.find((w) => w.work_id === selectedWorkId) || null;

  return (
    <div className="min-h-screen p-6" style={{ background: JJK.BG, color: JJK.TEXT }}>
      <div className="max-w-5xl mx-auto space-y-4">
        <header className="flex items-center justify-between">
          <h1 className="text-2xl font-bold" style={{ textShadow: glowColor(JJK.ACCENT, 0.4) }}>
            📖 Base Literaria
          </h1>
          <Link href="/chat" className="text-sm" style={{ color: JJK.ACCENT2 }}>
            ← Volver al chat
          </Link>
        </header>

        {error && (
          <div
            className="p-3 rounded text-sm"
            style={{ background: `${JJK.RED}22`, color: JJK.RED, border: `1px solid ${JJK.RED}55` }}
          >
            ⚠ {error}
          </div>
        )}

        <div className="grid md:grid-cols-[300px_1fr] gap-4 items-start">
          <StoryWorkSelector
            works={works}
            selectedWorkId={selectedWorkId}
            loading={loading}
            onSelect={handleSelect}
            onWorksChanged={loadWorks}
          />

          {!selectedWorkId ? (
            <div
              className="rounded-lg p-8 border text-center"
              style={{ borderColor: `${JJK.ACCENT}22`, background: JJK.PANEL }}
            >
              <p className="text-sm" style={{ color: `${JJK.TEXT}88` }}>
                {loading
                  ? "Cargando obras…"
                  : "Selecciona o crea una obra para gestionar personajes, canon y capítulos."}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div
                className="rounded-lg p-3 border text-sm"
                style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
              >
                <strong>{selectedWork?.title || selectedWorkId}</strong>
                {selectedWork?.description && (
                  <span style={{ color: `${JJK.TEXT}88` }}>
                    {" "}
                    — {selectedWork.description}
                  </span>
                )}
              </div>

              <div className="flex gap-1 flex-wrap">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setTab(t.id)}
                    className="px-3 py-2 rounded text-sm transition"
                    style={{
                      background: tab === t.id ? `${JJK.ACCENT}33` : "transparent",
                      border: `1px solid ${tab === t.id ? JJK.ACCENT : `${JJK.ACCENT}22`}`,
                      color: JJK.TEXT,
                    }}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {tab === "characters" && (
                <StoryCharacterEditor workId={selectedWorkId} />
              )}
              {tab === "canon" && <StoryCanonPanel workId={selectedWorkId} />}
              {tab === "chapters" && <StoryChapterPlanner workId={selectedWorkId} />}
              {tab === "coherence" && <StoryCoherencePanel workId={selectedWorkId} />}
              {tab === "session" && <StorySessionLink workId={selectedWorkId} />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
