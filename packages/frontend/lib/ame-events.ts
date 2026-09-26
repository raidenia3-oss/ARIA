"use client";

/**
 * Contrato de eventos AME — sincronización bidireccional AURA PC ↔ móvil.
 *
 * Todo evento sincronizable debe seguir este formato.
 * No sincroniza código ejecutable — solo datos, eventos y configuración.
 */

export const SCHEMA_VERSION = 1;

export type SyncEventType =
  | "chat_message"
  | "status_update"
  | "command_request"
  | "canon_event"
  | "character_update"
  | "session_change"
  | "reflection"
  | "plot_summary";

export interface CanonEventPayload {
  work_id: string;
  event_id: string;
  description: string;
  source: string;
}

export interface CharacterUpdatePayload {
  work_id: string;
  char_id: string;
  character: Record<string, unknown>;
}

export interface SessionChangePayload {
  work_id: string;
  session_id: string;
  status: string;
}

export interface ReflectionPayload {
  work_id: string;
  analysis: string;
  gaps: string[];
  plot_twists: string[];
}

export interface PlotSummaryPayload {
  work_id: string;
  summary: string;
}

export interface SyncEvent {
  eventId: string;
  deviceId: string;
  type: SyncEventType;
  createdAt: string;
  schemaVersion: number;
  payload: Record<string, unknown>;
}

export interface ChatMessagePayload {
  ameId: string;
  role: "user" | "ame";
  content: string;
  timestamp: string;
  imageUri?: string;
  audioUri?: string;
}

export interface StatusUpdatePayload {
  connected: boolean;
  auraAvailable: boolean;
  lastSync?: string | null;
  mode?: "local" | "remote";
}

export interface CommandRequestPayload {
  command: string;
  response?: unknown;
}

export interface SyncAck {
  eventId: string;
  status: "ok" | "error";
  error?: string;
  serverReceivedAt?: string;
}

const DEVICE_ID_KEY = "ame_device_id";

function isUuid(str: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(str);
}

export function generateDeviceId(): string {
  if (typeof window === "undefined") return "unknown-device";
  const saved = localStorage.getItem(DEVICE_ID_KEY);
  if (saved && isUuid(saved)) return saved;
  const id = crypto.randomUUID();
  localStorage.setItem(DEVICE_ID_KEY, id);
  return id;
}

export function createEvent(
  type: SyncEventType,
  payload: Record<string, unknown>,
  deviceId: string,
  opts?: { eventId?: string; createdAt?: string },
): SyncEvent {
  return {
    eventId: opts?.eventId ?? crypto.randomUUID(),
    deviceId,
    type,
    createdAt: opts?.createdAt ?? new Date().toISOString(),
    schemaVersion: SCHEMA_VERSION,
    payload,
  };
}

export function isValidEvent(obj: unknown): obj is SyncEvent {
  if (typeof obj !== "object" || obj === null) return false;
  const e = obj as Record<string, unknown>;
  return (
    typeof e.eventId === "string" &&
    typeof e.deviceId === "string" &&
    typeof e.type === "string" &&
    typeof e.createdAt === "string" &&
    typeof e.schemaVersion === "number" &&
    e.schemaVersion === SCHEMA_VERSION &&
    typeof e.payload === "object" &&
    e.payload !== null
  );
}

/**
 * Wraps a SyncEvent with legacy fields so the existing backend handler
 * (which reads `action` and `data`) can still process it without changes.
 */
export function toWireFormat(event: SyncEvent): Record<string, unknown> {
  return {
    eventId: event.eventId,
    deviceId: event.deviceId,
    type: event.type,
    createdAt: event.createdAt,
    schemaVersion: event.schemaVersion,
    payload: event.payload,
    action: event.type,
    data: event.payload,
  };
}

/**
 * Parses an incoming WebSocket message that may arrive in the new
 * contract format or the legacy `{ action, data }` format.
 */
export function parseIncomingMessage(msg: unknown): SyncEvent | null {
  if (isValidEvent(msg)) return msg as SyncEvent;

  if (typeof msg !== "object" || msg === null) return null;
  const m = msg as Record<string, unknown>;

  if (typeof m.action === "string" && typeof m.data === "object") {
    return {
      eventId: (m.eventId as string) ?? crypto.randomUUID(),
      deviceId: (m.deviceId as string) ?? "unknown",
      type: m.action as SyncEventType,
      createdAt: (m.createdAt as string) ?? new Date().toISOString(),
      schemaVersion: SCHEMA_VERSION,
      payload: (m.data as Record<string, unknown>) ?? {},
    };
  }

  return null;
}
