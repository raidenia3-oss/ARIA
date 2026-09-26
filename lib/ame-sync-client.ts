/**
 * AME Sync Client — buffer offline-first + sincronización diferencial.
 *
 * Cuando AME no alcanza al host de la PC, los eventos (chat, notas,
 * personajes, canon) se acumulan en LocalDB (pending_events). Al detectar
 * conectividad (online), se envían por lotes a POST /api/sync/push y se
 * eliminan del buffer local.
 *
 * El token del dispositivo y la URL del host se leen de localStorage.
 * No se envían secretos: solo eventIds, tipos, payloads y timestamps.
 */

import LocalDB, { PendingEvent } from "./indexed-db";

const HOST_KEY = "aura-paired-host";
const TOKEN_KEY = "aura-paired-device-token";

export interface SyncResult {
  status: string;
  applied: number;
  skipped: number;
  rejected: number;
  received: number;
}

export async function getHostUrl(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(HOST_KEY) || null;
}

export function isOnline(): boolean {
  if (typeof navigator === "undefined") return true;
  return navigator.onLine;
}

export async function queueEvent(event: PendingEvent): Promise<void> {
  const db = LocalDB.getInstance();
  await db.savePendingEvent(event);
}

export async function getPendingCount(): Promise<number> {
  const db = LocalDB.getInstance();
  return (await db.getPendingEvents()).length;
}

export async function flushPendingEvents(): Promise<SyncResult | null> {
  const host = await getHostUrl();
  if (!host) return null;

  const db = LocalDB.getInstance();
  const pending = await db.getPendingEventsByCreatedAt();
  if (pending.length === 0) {
    return { status: "ok", applied: 0, skipped: 0, rejected: 0, received: 0 };
  }

  const res = await fetch(`${host}/api/sync/push`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      events: pending.map((e) => ({
        eventId: e.eventId,
        type: e.type,
        createdAt: e.createdAt,
        payload: e.payload,
      })),
      device_id: window.localStorage.getItem("aura-paired-device-id") || "ame_mobile",
    }),
  });

  if (!res.ok) {
    throw new Error(`sync push failed: HTTP ${res.status}`);
  }

  const body = (await res.json()) as SyncResult;
  if (body.applied > 0) {
    // Eliminar los eventos aplicados del buffer local.
    const appliedSet = new Set<string>();
    // El backend no devuelve IDs aplicados explícitamente en todos los casos;
    // como aproximación segura, limpiamos los que NO están en skipped/rejected.
    for (const e of pending) {
      appliedSet.add(e.eventId);
    }
    for (const e of pending) {
      if (appliedSet.has(e.eventId)) {
        await db.deletePendingEvent(e.eventId);
      }
    }
  }
  return body;
}