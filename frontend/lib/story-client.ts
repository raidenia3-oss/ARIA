/**
 * Cliente HTTP tipado para la base literaria (/api/story).
 * Usa el proxy local /api/story/[...path] para no exponer el backend
 * ni credenciales en el cliente. Nunca incluye tokens.
 */

import type {
  FullConsistencyResult,
  SessionContext,
  StoryCharacter,
  StoryChapter,
  StoryConflict,
  StoryEvent,
  StoryProgress,
  StoryWork,
  ChapterStatus,
} from "./story-types";

export class StoryApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "StoryApiError";
    this.status = status;
  }
}

async function storyFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/story${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* respuesta sin JSON */
    }
    throw new StoryApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

// --- Obras ---

export function listWorks(): Promise<{ works: StoryWork[]; count: number }> {
  return storyFetch("/works");
}

export function createWork(payload: {
  work_id: string;
  title: string;
  universe: string;
  description: string;
  author: string;
}): Promise<{ status: string; work_id: string; title?: string }> {
  return storyFetch("/works", { method: "POST", body: JSON.stringify(payload) });
}

export function getWork(workId: string): Promise<StoryWork> {
  return storyFetch(`/works/${encodeURIComponent(workId)}`);
}

export function deleteWork(
  workId: string
): Promise<{ status: string; work_id: string }> {
  return storyFetch(`/works/${encodeURIComponent(workId)}`, { method: "DELETE" });
}

// --- Personajes ---

export function listCharacters(
  workId: string
): Promise<{ characters: StoryCharacter[]; count: number }> {
  return storyFetch(`/${encodeURIComponent(workId)}/characters`);
}

export function upsertCharacter(
  workId: string,
  charId: string,
  payload: Partial<StoryCharacter>
): Promise<{ status: string; char_id: string; character: StoryCharacter }> {
  return storyFetch(
    `/${encodeURIComponent(workId)}/characters/${encodeURIComponent(charId)}`,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

export function deleteCharacter(
  workId: string,
  charId: string
): Promise<{ status?: string; error?: string }> {
  return storyFetch(
    `/${encodeURIComponent(workId)}/characters/${encodeURIComponent(charId)}`,
    { method: "DELETE" }
  );
}

// --- Canon y continuidad ---

export function addEvent(
  workId: string,
  kind: "canon" | "continuity",
  payload: { description: string; timestamp: number; scene_ref: string; source: string }
): Promise<{ status: string; event_id: string; type: string }> {
  return storyFetch(`/${encodeURIComponent(workId)}/${kind}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listEvents(
  workId: string,
  kind: "canon" | "continuity"
): Promise<{ events: StoryEvent[]; count: number }> {
  return storyFetch(`/${encodeURIComponent(workId)}/${kind}`);
}

export function getChronology(
  workId: string,
  maxEvents = 100
): Promise<{ events: StoryEvent[]; count: number }> {
  return storyFetch(
    `/${encodeURIComponent(workId)}/chronology?max_events=${maxEvents}`
  );
}

export function getConflicts(
  workId: string
): Promise<{ conflicts: StoryConflict[]; count: number }> {
  return storyFetch(`/${encodeURIComponent(workId)}/conflicts`);
}

// --- Capítulos y escenas ---

export function listChapters(
  workId: string
): Promise<{ chapters: StoryChapter[]; count: number; progress: StoryProgress }> {
  return storyFetch(`/${encodeURIComponent(workId)}/chapters`);
}

export function createChapter(
  workId: string,
  payload: { title: string; order: number; beat_summary: string }
): Promise<{ status: string; chapter_id: string; chapter: StoryChapter }> {
  return storyFetch(`/${encodeURIComponent(workId)}/chapters`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateChapterStatus(
  workId: string,
  chapterId: string,
  status: ChapterStatus
): Promise<{ status: string; chapter_status?: string; error?: string }> {
  return storyFetch(
    `/${encodeURIComponent(workId)}/chapters/${encodeURIComponent(chapterId)}`,
    { method: "PUT", body: JSON.stringify({ status }) }
  );
}

export function addScene(
  workId: string,
  chapterId: string,
  scene: { title?: string; description?: string }
): Promise<{ status: string; scene_id: string; error?: string }> {
  return storyFetch(
    `/${encodeURIComponent(workId)}/chapters/${encodeURIComponent(chapterId)}/scenes`,
    { method: "POST", body: JSON.stringify({ scene }) }
  );
}

// --- Coherencia ---

export function checkConsistency(
  workId: string,
  charId: string,
  text: string
): Promise<FullConsistencyResult> {
  return storyFetch(`/${encodeURIComponent(workId)}/check-consistency`, {
    method: "POST",
    body: JSON.stringify({ char_id: charId, text }),
  });
}

// --- Sesión de chat ---

export function bindSession(
  sessionId: string,
  payload: { work_id: string; character_id: string }
): Promise<{ status: string; session_id: string; context: SessionContext }> {
  return storyFetch(
    `/sessions/${encodeURIComponent(sessionId)}/context`,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

export function unbindSession(
  sessionId: string
): Promise<{ cleared?: boolean; status?: string }> {
  return storyFetch(`/sessions/${encodeURIComponent(sessionId)}/context`, {
    method: "DELETE",
  });
}

export function getSessionContext(
  sessionId: string
): Promise<{ status: string; active: boolean; context?: SessionContext }> {
  return storyFetch(`/sessions/${encodeURIComponent(sessionId)}/context`);
}

export interface MobileStoryContext {
  status: string;
  active: boolean;
  session_id?: string;
  work_id: string | null;
  character_id: string | null;
  work_title?: string;
  character_name?: string;
}

export function getMobileStoryContext(sessionId: string): Promise<MobileStoryContext> {
  return fetch(`/api/mobile/story?session_id=${encodeURIComponent(sessionId)}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  }).then((res) => {
    if (!res.ok) {
      throw new StoryApiError(`Error ${res.status}`, res.status);
    }
    return res.json() as Promise<MobileStoryContext>;
  });
}
