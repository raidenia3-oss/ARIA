/**
 * Tipos de la base literaria AURA/AME.
 * Reflejan EXACTAMENTE los modelos de backend/story_memory/ y
 * las respuestas de backend/story_routes.py (contrato /api/story).
 */

export interface StoryWork {
  work_id: string;
  title: string;
  universe: string;
  description: string;
  author: string;
  created_at: number;
  updated_at: number;
}

export interface StoryCharacter {
  char_id: string;
  name: string;
  aliases: string[];
  species: string;
  age: number | null;
  voice: string;
  personality: string[];
  objectives: string[];
  conflicts: string[];
  relationships: Record<string, string>;
  backstory: string;
  created_at?: number;
  updated_at?: number;
}

export interface StoryEvent {
  event_id: string;
  description: string;
  timestamp: number;
  scene_ref: string;
  source: string;
  certainty: string;
  type?: string;
  created_at?: number;
  updated_at?: number;
}

export interface StoryScene {
  scene_id: string;
  title?: string;
  description?: string;
  created_at?: number;
  [key: string]: unknown;
}

export type ChapterStatus =
  | "planned"
  | "in_progress"
  | "drafted"
  | "revised"
  | "completed";

export interface StoryChapter {
  chapter_id: string;
  title: string;
  order: number;
  beat_summary: string;
  scenes: StoryScene[];
  related_canon: string[];
  status: ChapterStatus;
  created_at: number;
  updated_at?: number;
}

export interface StoryProgress {
  total_chapters: number;
  completed: number;
  in_progress: number;
  planned: number;
  progress_percent: number;
  chapters: StoryChapter[];
}

export interface ConsistencyViolation {
  type: string;
  characteristic: string;
  description: string;
}

export interface ConsistencyCheck {
  name: string;
  result: "pass" | "fail" | "warn";
  characteristic?: string;
  characteristics?: string[];
}

export interface CharacterConsistency {
  status: string;
  error?: string;
  checks: ConsistencyCheck[];
  violations: ConsistencyViolation[];
  text_length?: number;
}

export interface CanonConsistency {
  status: "canonical" | "contradiction";
  matches: Array<{ event_id: string; description: string }>;
  contradictions: Array<{
    event_id: string;
    description: string;
    message: string;
  }>;
  total_canon_events: number;
}

export interface SourceClassification {
  classification: "canon" | "interpretation" | "invented";
  reason?: string;
  matches?: Array<{ event_id: string; description: string }>;
}

export interface FullConsistencyResult {
  status: "pass" | "fail";
  timestamp: number;
  character_consistency: CharacterConsistency;
  canon_consistency: CanonConsistency;
  source_classification: SourceClassification;
  overall_pass: boolean;
}

export interface StoryConflict {
  [key: string]: unknown;
}

export interface SessionContext {
  session_id: string;
  work_id: string;
  character_id: string;
  extra?: Record<string, unknown> | null;
  [key: string]: unknown;
}

export const CHAPTER_STATUSES: ChapterStatus[] = [
  "planned",
  "in_progress",
  "drafted",
  "revised",
  "completed",
];
