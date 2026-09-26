"use client";

/**
 * AME Sync Manager — capa de integración entre state machine, IndexedDB, WebSocket y UI.
 *
 * Responsabilidades:
 * - Detectar si AURA PC está disponible (REST discovery ping).
 * - Gestionar cola offline de eventos en IndexedDB.
 * - Reconectar con backoff exponencial.
 * - Enviar eventos pendientes al reconectar, deduplicando por eventId.
 * - Tracking de lastSync.
 * - Proveer datos simulados marcados como "demo" cuando AURA no responde.
 */

import LocalDB, { type PendingEvent } from "./indexed-db";
import AmestatusMachine, { type Amestatus } from "./ame-state-machine";
import AmewebSocketClient, { type AmewebSocketStatus } from "./ame-websocket";
import {
  createEvent,
  type SyncEvent,
  type SyncEventType,
  type CanonEventPayload,
  type CharacterUpdatePayload,
  type SessionChangePayload,
  type ReflectionPayload,
  type PlotSummaryPayload,
} from "./ame-events";
import {
  type AuraHost,
  discoverAuraHost,
  getSavedHost,
  saveManualHost,
} from "./ame-mdns";

export type RealtimeEvent =
  | { type: "canon_event"; payload: CanonEventPayload }
  | { type: "character_update"; payload: CharacterUpdatePayload }
  | { type: "session_change"; payload: SessionChangePayload }
  | { type: "reflection"; payload: ReflectionPayload }
  | { type: "plot_summary"; payload: PlotSummaryPayload };

export const REALTIME_EVENTS_BUFFER_LIMIT = 100;

const BACKEND_URL = process.env.NEXT_PUBLIC_AURA_BACKEND_URL || "http://localhost:8000";
const DISCOVERY_TIMEOUT_MS = 3000;
const AURA_CHECK_INTERVAL_MS = 5000;

export interface AmestatusState {
  ameStatus: Amestatus;
  wsStatus: AmewebSocketStatus;
  auraAvailable: boolean;
  internetAvailable: boolean;
  lastSync: string | null;
  pendingCount: number;
  deviceId: string;
  demoMode: boolean;
  realtimeEvents: RealtimeEvent[];
  realtimeStatus: "live" | "buffered" | "offline";
}

export interface DemoAME {
  id: string;
  name: string;
  status: "online" | "offline";
  lastActivity: string;
  unreadCount: number;
}

const DEMO_AMES: DemoAME[] = [
  {
    id: "ame_core",
    name: "AURA-Core",
    status: "offline",
    lastActivity: new Date().toISOString(),
    unreadCount: 0,
  },
  {
    id: "ame_analytics",
    name: "Analytics-AME",
    status: "offline",
    lastActivity: new Date(Date.now() - 3600000).toISOString(),
    unreadCount: 0,
  },
  {
    id: "ame_integrations",
    name: "Integrations-AME",
    status: "offline",
    lastActivity: new Date(Date.now() - 7200000).toISOString(),
    unreadCount: 0,
  },
];

export class AmestatusSyncManager {
  private static instance: AmestatusSyncManager;
  private stateMachine: AmestatusMachine;
  private db: LocalDB;
  private deviceId: string;
  private ws: AmewebSocketClient | null = null;
  private listeners = new Set<(state: AmestatusState) => void>();
  private auraCheckTimer: ReturnType<typeof setInterval> | null = null;
  private authToken: string | null = null;
  private lastWsStatus: AmewebSocketStatus = "disconnected";
  private initialized = false;
  private resolvedBackendUrl: string | null = null;
  private realtimeEvents: RealtimeEvent[] = [];
  private realtimeListeners = new Set<(event: RealtimeEvent) => void>();
  private realtimeSubscribedWork: string | null = null;

  private constructor() {
    this.stateMachine = new AmestatusMachine("independent");
    this.db = LocalDB.getInstance();
    this.deviceId = "";
  }

  static getInstance(): AmestatusSyncManager {
    if (!AmestatusSyncManager.instance) {
      AmestatusSyncManager.instance = new AmestatusSyncManager();
    }
    return AmestatusSyncManager.instance;
  }

  async init(): Promise<void> {
    if (this.initialized) return;
    await this.db.init();
    this.deviceId = (await this.db.getConfig<string>("deviceId")) || "";
    if (!this.deviceId) {
      this.deviceId = this.generateDeviceId();
      await this.db.saveConfig("deviceId", this.deviceId);
    }
    this.authToken = (await this.db.getConfig<string>("authToken")) || null;

    this.setupStateMachine();
    this.startAuraCheck();
    this.startPullDeltas();
    this.initialized = true;
    this.emitChange();
  }

  private async resolveBackendFromPairing(): Promise<void> {
    try {
      const profile = await getPairingProfile();
      const host = profile.local_ips?.[0] || profile.hostname;
      if (host) {
        this.resolvedBackendUrl = `http://${host}:${profile.port}`;
        return;
      }
    } catch {
      this.resolvedBackendUrl = null;
    }
    // BLOQUE 35: Auto-discovery hook — escaneo de subred + fallback manual.
    const discovered = await discoverAuraHost(this.getEffectiveBackendUrl());
    if (discovered) {
      this.resolvedBackendUrl = discovered.baseUrl;
      if (discovered.source === "manual") saveManualHost(discovered.host);
    }
  }

  getEffectiveBackendUrl(): string {
    return this.resolvedBackendUrl || BACKEND_URL;
  }

  private setupStateMachine(): void {
    this.stateMachine.subscribe(this.handleStateChange.bind(this));
  }

   private async handleStateChange(state: Amestatus): Promise<void> {
    if (state === "reconnecting" && !this.ws) {
      await this.attemptWebSocketConnection();
    }
    if (state === "connected" && this.ws && this.ws.isConnected() && this.ws.getStatus() === "connected") {
      this.flushPendingEvents();
    }
    this.emitChange();
  }

  getDeviceId(): string {
    return this.deviceId;
  }

  setAuthToken(token: string): void {
    this.authToken = token;
    this.db.saveConfig("authToken", token);
  }

  private async attemptWebSocketConnection(): Promise<void> {
    if (!this.deviceId) return;

    this.ws = new AmewebSocketClient({
      backendUrl: BACKEND_URL,
      deviceId: this.deviceId,
      authToken: this.authToken ?? undefined,
      streamEndpoint: "stream",
      onOpen: () => {
        this.stateMachine.transition("reconnect_success");
        this.flushPendingEvents();
        if (this.realtimeSubscribedWork && this.ws) {
          this.ws.subscribe(this.realtimeSubscribedWork);
        }
      },
      onClose: (clean: boolean) => {
        if (clean) {
          this.stateMachine.transition("aura_lost");
        } else {
          this.stateMachine.transition("aura_lost");
          this.stateMachine.transition("reconnect_attempt");
        }
      },
      onError: (err: Error) => {
        console.warn("WebSocket connection error:", err.message);
        this.stateMachine.transition("auth_failed");
      },
      onMessage: this.handleWsMessage.bind(this),
      onStatusChange: (status: AmewebSocketStatus) => {
        this.lastWsStatus = status;
        this.emitChange();
      },
    });

    this.ws.setStateMachine(this.stateMachine);
    this.ws.connect();
  }

  private async handleWsMessage(msg: unknown): Promise<void> {
    const state = this.stateMachine.getState();
    if (state === "syncing" || state === "reconnecting" || state === "connected") {
      this.stateMachine.transition("sync_completed");
    }

    if (typeof msg === "object" && msg !== null) {
      const m = msg as { eventId?: string; type?: string; payload?: Record<string, unknown> };
      if (m.eventId) {
        try {
          await this.db.deletePendingEvent(m.eventId);
        } catch (err) {
          console.warn("Failed to delete pending event on ack:", err);
        }
      }

      const realtimeEvent = this.parseRealtimeEvent(m);
      if (realtimeEvent) {
        this.bufferRealtimeEvent(realtimeEvent);
        this.notifyRealtimeListeners(realtimeEvent);
      }
    }

    this.emitChange();
  }

  private parseRealtimeEvent(msg: { type?: string; payload?: Record<string, unknown> }): RealtimeEvent | null {
    const t = msg.type ?? msg.payload?.type;
    const payload = msg.payload ?? {};
    switch (t) {
      case "canon_event":
        return { type: "canon_event", payload: payload as unknown as CanonEventPayload };
      case "character_update":
        return { type: "character_update", payload: payload as unknown as CharacterUpdatePayload };
      case "session_change":
        return { type: "session_change", payload: payload as unknown as SessionChangePayload };
      case "reflection":
        return { type: "reflection", payload: payload as unknown as ReflectionPayload };
      case "plot_summary":
        return { type: "plot_summary", payload: payload as unknown as PlotSummaryPayload };
      default:
        return null;
    }
  }

  private bufferRealtimeEvent(event: RealtimeEvent): void {
    this.realtimeEvents.push(event);
    if (this.realtimeEvents.length > REALTIME_EVENTS_BUFFER_LIMIT) {
      this.realtimeEvents.shift();
    }
  }

  subscribeRealtime(listener: (event: RealtimeEvent) => void): () => void {
    this.realtimeListeners.add(listener);
    return () => {
      this.realtimeListeners.delete(listener);
    };
  }

  subscribeRealtimeWork(workId: string): void {
    this.realtimeSubscribedWork = workId;
    if (this.ws && this.ws.isConnected()) {
      this.ws.subscribe(workId);
    }
  }

  private notifyRealtimeListeners(event: RealtimeEvent): void {
    for (const listener of this.realtimeListeners) {
      try {
        listener(event);
      } catch (err) {
        console.warn("Realtime listener error:", err);
      }
    }
  }

  getRealtimeEvents(): RealtimeEvent[] {
    return [...this.realtimeEvents];
  }

  getRealtimeStatus(): "live" | "buffered" | "offline" {
    const state = this.stateMachine.getState();
    if (state === "independent" || state === "offline_pending") return "offline";
    return this.realtimeEvents.length > 0 ? "live" : "buffered";
  }

  private startAuraCheck(): void {
    if (this.auraCheckTimer) clearInterval(this.auraCheckTimer);
    this.auraCheckTimer = setInterval(() => {
      this.checkAuraAvailability();
    }, AURA_CHECK_INTERVAL_MS);
    this.checkAuraAvailability();
  }

   private async checkAuraAvailability(): Promise<boolean> {
    if (!navigator.onLine) {
      this.stateMachine.transition("internet_lost");
      return false;
    }

    try {
      const headers: Record<string, string> = {};
      if (this.authToken) headers["Authorization"] = `Bearer ${this.authToken}`;

      let baseUrl = this.getEffectiveBackendUrl();
      const res = await fetch(`${baseUrl}/api/mobile/discovery`, {
        method: "GET",
        headers,
        signal: AbortSignal.timeout(DISCOVERY_TIMEOUT_MS),
      });

        if (res.ok) {
        const data = await res.json();
        await this.db.saveConfig("auraInfo", data);
        const currentState = this.stateMachine.getState();
        if (currentState === "independent" || currentState === "offline_pending" || currentState === "revoked") {
          this.stateMachine.transition("aura_detected");
        }
        if (currentState === "disconnected" || currentState === "reconnecting" || currentState === "auth_failed") {
          this.stateMachine.transition("aura_detected");
        }
        if (!this.ws) {
          await this.attemptWebSocketConnection();
        } else if (this.ws.isConnected() && this.ws.getStatus() === "connected") {
          this.flushPendingEvents();
        }
        return true;
      }
      return false;
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err);

      if (error.includes("fetch") || error.includes("ECONNREFUSED") || error.includes("timeout")) {
        this.stateMachine.transition("aura_lost");
        if (!this.ws) {
          this.stateMachine.transition("reconnect_attempt");
        }
        if (!this.resolvedBackendUrl) {
          this.resolveBackendFromPairing().catch(() => {});
        }
      }
      return false;
    }
  }

  async queueEvent(
    type: SyncEventType,
    payload: Record<string, unknown>,
  ): Promise<SyncEvent> {
    if (!this.deviceId) {
      this.deviceId = this.generateDeviceId();
      await this.db.saveConfig("deviceId", this.deviceId);
    }

    const event = createEvent(type, payload, this.deviceId);

    const pending: PendingEvent = {
      eventId: event.eventId,
      createdAt: event.createdAt,
      type: event.type,
      payload: event.payload,
    };
    await this.db.savePendingEvent(pending);

    this.stateMachine.transition("offline_pending");
    this.emitChange();
    return event;
  }

  async flushPendingEvents(): Promise<void> {
    const pending = await this.db.getPendingEventsByCreatedAt();
    if (pending.length === 0) {
      const lastSync = new Date().toISOString();
      await this.db.setLastSync(lastSync);
      this.emitChange();
      return;
    }

    const wsConnected = this.ws && this.isOnline() && this.ws.isConnected() && this.ws.getStatus() === "connected";
    if (!wsConnected) {
      this.stateMachine.transition("offline_save");
      return;
    }

    for (const evt of pending) {
      const event: SyncEvent = {
        eventId: evt.eventId,
        deviceId: this.deviceId,
        type: evt.type as SyncEventType,
        createdAt: evt.createdAt,
        schemaVersion: 1,
        payload: evt.payload,
      };
      try {
        this.ws!.send(event);
        await this.db.saveEvent(event);
      } catch (err) {
        console.warn("Failed to flush pending event:", err instanceof Error ? err.message : String(err));
      }
    }

    const lastSync = new Date().toISOString();
    await this.db.setLastSync(lastSync);
    this.emitChange();
  }

  async getChatHistory(ameId: string): Promise<Array<{ role: string; text: string; timestamp: string }>> {
    return this.db.getChatHistory(ameId);
  }

  async saveChatMessage(ameId: string, role: "user" | "ame", text: string): Promise<void> {
    await this.db.saveChatMessage({ role, text, ameId });

    if (role === "user") {
      await this.queueEvent("chat_message", {
        ameId,
        role,
        content: text,
        timestamp: new Date().toISOString(),
      } as Record<string, unknown>);
    }
  }

  async flushOfflineToRest(): Promise<boolean> {
    const pending = await this.db.getPendingEventsByCreatedAt();
    if (pending.length === 0) return true;

    const baseUrl = this.getEffectiveBackendUrl();
    try {
      const res = await fetch(`${baseUrl}/api/sync/push`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: this.deviceId,
          session_id: this.deviceId.replace("ame_", ""),
          last_sync_timestamp: await this.db.getLastSync(),
          events: pending.map((e) => ({
            eventId: e.eventId,
            type: e.type,
            payload: e.payload,
            createdAt: e.createdAt,
          })),
        }),
        signal: AbortSignal.timeout(15000),
      });
      if (!res.ok) return false;
      const result = await res.json();
      if (result.status === "ok") {
        for (const evt of pending) {
          await this.db.deletePendingEvent(evt.eventId);
        }
        await this.db.setLastSync(new Date().toISOString());
        this.emitChange();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  /**
   * Pull deltas from PC since last checkpoint.
   * Runs on a timer (5s default) when aura is available.
   */
  private pullTimer: ReturnType<typeof setInterval> | null = null;
  private lastPullCheckpoint: number = 0;

  async pullDeltasFromPC(): Promise<{ applied: number; checkpoint: number }> {
    if (!this.isOnline() || !this.deviceId) {
      return { applied: 0, checkpoint: this.lastPullCheckpoint };
    }

    const baseUrl = this.getEffectiveBackendUrl();
    try {
      const res = await fetch(
        `${baseUrl}/api/sync/pull?client_id=${encodeURIComponent(this.deviceId)}&since=${this.lastPullCheckpoint}&limit=200`,
        {
          method: "GET",
          headers: { "Content-Type": "application/json" },
          signal: AbortSignal.timeout(10000),
        }
      );

      if (!res.ok) {
        console.warn(`Pull sync failed: HTTP ${res.status}`);
        return { applied: 0, checkpoint: this.lastPullCheckpoint };
      }

      const data = await res.json();
      const events: Array<{
        id: string;
        type: string;
        payload: unknown;
        createdAt: number;
        status: string;
      }> = data.events || [];

      let applied = 0;
      for (const evt of events) {
        const existing = await this.db.getEvent(evt.id).catch(() => undefined);
        if (existing) continue;

        await this.db.saveEvent({
          eventId: evt.id,
          deviceId: this.deviceId,
          type: evt.type as any,
          createdAt: new Date(evt.createdAt * 1000).toISOString(),
          schemaVersion: 1,
          payload: (evt.payload as Record<string, unknown>) || {},
        });

        if (evt.type === "chat_message" || evt.type === "chat_received") {
          const p = evt.payload as Record<string, unknown>;
          if (p && (p.role || p.content)) {
            await this.db.saveChatMessage({
              role: (p.role as "user" | "ame") || "ame",
              text: (p.content as string) || (p.text as string) || "",
              ameId: (p.ameId as string) || "ame_core",
            });
          }
        }

        applied++;
      }

      if (data.checkpoint) {
        this.lastPullCheckpoint = data.checkpoint;
        await this.db.saveConfig("lastPullCheckpoint", data.checkpoint);
      }

      this.emitChange();
      return { applied, checkpoint: this.lastPullCheckpoint };
    } catch (err) {
      console.warn("Pull deltas error:", err instanceof Error ? err.message : String(err));
      return { applied: 0, checkpoint: this.lastPullCheckpoint };
    }
  }

  startPullDeltas(intervalMs: number = 5000): void {
    if (this.pullTimer) {
      clearInterval(this.pullTimer);
    }
    this.db.getConfig<number>("lastPullCheckpoint").then((cp) => {
      if (cp) this.lastPullCheckpoint = cp;
    });
    this.pullTimer = setInterval(() => {
      this.pullDeltasFromPC().catch(() => {});
    }, intervalMs);
    this.pullDeltasFromPC().catch(() => {});
  }

  stopPullDeltas(): void {
    if (this.pullTimer) {
      clearInterval(this.pullTimer);
      this.pullTimer = null;
    }
  }

  async getPendingCount(): Promise<number> {
    const hasPending = await this.db.hasPendingEvents();
    return hasPending ? 1 : 0;
  }

  isOnline(): boolean {
    const state = this.stateMachine.getState();
    return state === "connected" || state === "syncing" || state === "delegating";
  }

  async getDemoStatus(): Promise<{ mode: string; ames: DemoAME[] }> {
    return {
      mode: "demo",
      ames: DEMO_AMES,
    };
  }

  isAuraOffline(): boolean {
    return !navigator.onLine ? false : this.stateMachine.getState() === "offline_pending" || this.stateMachine.getState() === "independent";
  }

  isInternetOffline(): boolean {
    return !navigator.onLine || this.stateMachine.getState() === "offline_pending";
  }

  getState(): AmestatusState {
    const state = this.stateMachine.getState();
    const isOffline = state === "offline_pending" || state === "independent";
    return {
      ameStatus: state,
      wsStatus: this.lastWsStatus,
      auraAvailable: !isOffline,
      internetAvailable: navigator.onLine,
      lastSync: null,
      pendingCount: 0,
      deviceId: this.deviceId,
      demoMode: this.isAuraOffline() || this.isInternetOffline(),
      realtimeEvents: [...this.realtimeEvents],
      realtimeStatus: this.getRealtimeStatus(),
    };
  }

  async getStateAsync(): Promise<AmestatusState> {
    const state = this.stateMachine.getState();
    const isOffline = state === "offline_pending" || state === "independent";
    const lastSync = await this.db.getLastSync();
    const pendingCount = await this.db.hasPendingEvents();
    return {
      ameStatus: state,
      wsStatus: this.lastWsStatus,
      auraAvailable: !isOffline,
      internetAvailable: navigator.onLine,
      lastSync,
      pendingCount: pendingCount ? 1 : 0,
      deviceId: this.deviceId,
      demoMode: this.isAuraOffline() || this.isInternetOffline(),
      realtimeEvents: [...this.realtimeEvents],
      realtimeStatus: this.getRealtimeStatus(),
    };
  }

  subscribe(listener: (state: AmestatusState) => void): () => void {
    this.listeners.add(listener);
    this.emitChange();
    return () => {
      this.listeners.delete(listener);
    };
  }

  private emitChange(): void {
    for (const listener of this.listeners) {
      this.getStateAsync().then((state) => listener(state)).catch(() => {});
    }
  }

  private generateDeviceId(): string {
    return crypto.randomUUID();
  }

  destroy(): void {
    if (this.auraCheckTimer) {
      clearInterval(this.auraCheckTimer);
      this.auraCheckTimer = null;
    }
    this.stopPullDeltas();
    this.ws?.disconnect();
    this.ws = null;
  }
}

export default AmestatusSyncManager;

export interface PairingProfile {
  name: string;
  hostname: string;
  local_ips: string[];
  port: number;
  ws_port: number;
  pairing_token: string;
  pairing_token_ttl: number;
  api_version: string;
  timestamp: number;
}

export interface HealthCheckResult {
  status: string;
  hostname: string;
  local_ip: string;
  port: number;
  latency_ms: number;
  timestamp: number;
}

export async function getPairingProfile(
  backendUrl: string = BACKEND_URL
): Promise<PairingProfile> {
  const res = await fetch(`${backendUrl}/api/mobile/pairing-profile`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      ...(process.env.NEXT_PUBLIC_AURA_API_KEY
        ? { "X-API-Key": process.env.NEXT_PUBLIC_AURA_API_KEY }
        : {}),
    },
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) {
    throw new Error(`Pairing profile request failed: ${res.status}`);
  }
  return res.json() as Promise<PairingProfile>;
}

export async function checkLocalHealth(
  backendUrl: string = BACKEND_URL
): Promise<HealthCheckResult> {
  const start = Date.now();
  const res = await fetch(`${backendUrl}/api/mobile/health-check`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      ...(process.env.NEXT_PUBLIC_AURA_API_KEY
        ? { "X-API-Key": process.env.NEXT_PUBLIC_AURA_API_KEY }
        : {}),
    },
    signal: AbortSignal.timeout(3000),
  });
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  const data = await res.json() as HealthCheckResult;
  data.latency_ms = Date.now() - start;
  return data;
}
