"use client";

/**
 * AME Sync Client — API simplificada para componentes que consumen
 * sincronización offline-first con la PC AURA.
 *
 * Envoltura `AmestatusSyncManager` exponiendo:
 * - isOnline: estado de conectividad AURA LAN.
 * - queueEvent: encola un evento para sync diferencial.
 * - flushPendingEvents: descarga la cola offline (WebSocket o REST fallback).
 * - getPendingCount: número de eventos pendientes (0 = sincronizado).
 *
 * No accede directamente al filesystem; utiliza IndexedDB internamente.
 */

import AmestatusSyncManager from "./ame-sync";
import type { SyncEvent, SyncEventType } from "./ame-events";

const manager = AmestatusSyncManager.getInstance();

export function isOnline(): boolean {
  return manager.isOnline();
}

export async function queueEvent(
  type: SyncEventType,
  payload: Record<string, unknown>,
): Promise<SyncEvent> {
  return manager.queueEvent(type, payload);
}

export async function flushPendingEvents(): Promise<boolean> {
  if (manager.isOnline()) {
    try {
      await manager.flushPendingEvents();
      const remaining = await manager.getPendingCount();
      return remaining === 0;
    } catch {
      return false;
    }
  }
  return manager.flushOfflineToRest();
}

export async function getPendingCount(): Promise<number> {
  return manager.getPendingCount();
}

export function getBackendUrl(): string {
  return manager.getEffectiveBackendUrl();
}

export default { isOnline, queueEvent, flushPendingEvents, getPendingCount, getBackendUrl };
