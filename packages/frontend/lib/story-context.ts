"use client";

export interface MobileStoryContextState {
  active: boolean;
  workId: string;
  characterId: string;
  workTitle: string;
  characterName: string;
}

export interface ConsistencyIndicatorState {
  status: "idle" | "checking" | "pass" | "fail";
  pass: boolean;
  violations: number;
}

import type { FullConsistencyResult, SessionContext, StoryWork, StoryCharacter } from "./story-types";
import { getSessionContext, bindSession, unbindSession, listWorks, listCharacters, checkConsistency, StoryApiError } from "./story-client";

export async function getMobileSessionContext(sessionId: string): Promise<{ active: boolean; context?: SessionContext }> {
  try {
    const res = await getSessionContext(sessionId);
    return { active: res.active, context: res.active ? res.context : undefined };
  } catch (err: unknown) {
    const msg = err instanceof StoryApiError ? err.message : "Error al consultar contexto";
    return { active: false };
  }
}

export async function resolveSessionDetails(
  sessionId: string
): Promise<MobileStoryContextState | null> {
  const { active, context } = await getMobileSessionContext(sessionId);
  if (!active || !context) return null;
  try {
    const [workRes, charRes] = await Promise.all([
      listWorks().catch(() => ({ works: [] as StoryWork[] })),
      context.character_id ? listCharacters(context.work_id).catch(() => ({ characters: [] as StoryCharacter[] })) : { characters: [] as StoryCharacter[] },
    ]);
    const work = workRes.works.find((w) => w.work_id === context.work_id) ?? null;
    const character = charRes.characters.find((c) => c.char_id === context.character_id) ?? null;
    return {
      active: true,
      workId: context.work_id,
      characterId: context.character_id,
      workTitle: work?.title ?? context.work_id,
      characterName: character?.name ?? context.character_id,
    };
  } catch {
    return {
      active: true,
      workId: context.work_id,
      characterId: context.character_id,
      workTitle: context.work_id,
      characterName: context.character_id,
    };
  }
}

export async function checkMobileConsistency(
  workId: string,
  charId: string,
  text: string
): Promise<ConsistencyIndicatorState> {
  if (!workId || !charId || !text.trim()) {
    return { status: "idle", pass: false, violations: 0 };
  }
  try {
    const res = await checkConsistency(workId, charId, text.trim());
    return {
      status: "pass",
      pass: res.overall_pass,
      violations: (res.character_consistency.violations?.length ?? 0) + (res.canon_consistency.contradictions?.length ?? 0),
    };
  } catch {
    return { status: "idle", pass: false, violations: 0 };
  }
}
