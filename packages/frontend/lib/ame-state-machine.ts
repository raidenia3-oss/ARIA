"use client";

/**
 * Máquina de estados de AME.
 *
 * Estados:
 *   independent         — AURA y AME operan de forma autónoma
 *   discovering         — Buscando instancia AURA en LAN
 *   pairing             — Registro de dispositivo, esperando aprobación
 *   connecting          — Conexión WebSocket en progreso
 *   connected           — WebSocket conectado y autenticado
 *   delegating          — Tarea delegada a AURA en ejecución
 *   syncing             — En progreso de sincronización
 *   disconnected        — WS cerrado, retry pendiente
 *   reconnecting        — Backoff activo tratando de reconectar
 *   offline_pending     — Eventos pendientes, AURA offline
 *   revoked             — Dispositivo revocado
 *   auth_failed         — Falló autenticación (token inválido/expirado)
 */

export type Amestatus =
  | "independent"
  | "discovering"
  | "pairing"
  | "connecting"
  | "connected"
  | "delegating"
  | "syncing"
  | "disconnected"
  | "reconnecting"
  | "offline_pending"
  | "revoked"
  | "auth_failed";

export type AmestatusEvent =
  | "aura_detected"
  | "start_pairing"
  | "pairing_approved"
  | "pairing_rejected"
  | "connected"
  | "aura_lost"
  | "start_delegate"
  | "delegate_complete"
  | "sync_started"
  | "sync_completed"
  | "sync_failed"
  | "offline_save"
  | "reconnect_attempt"
  | "reconnect_success"
  | "offline_pending"
  | "revoked"
  | "auth_failed"
  | "auth_restored"
  | "internet_lost"
  | "internet_restored"
  | "manual_reset";

export interface StateTransitionResult {
  from: Amestatus;
  to: Amestatus;
  event: AmestatusEvent;
}

const TRANSITIONS: Record<Amestatus, Partial<Record<AmestatusEvent, Amestatus>>> = {
  independent: {
    aura_detected: "discovering",
    start_pairing: "pairing",
    internet_lost: "offline_pending",
    manual_reset: "independent",
  },
  discovering: {
    pairing_approved: "connecting",
    pairing_rejected: "independent",
    connected: "connected",
    aura_lost: "offline_pending",
    internet_lost: "offline_pending",
    manual_reset: "independent",
  },
  pairing: {
    pairing_approved: "connecting",
    pairing_rejected: "independent",
    connected: "connected",
    aura_lost: "offline_pending",
    internet_lost: "offline_pending",
    manual_reset: "independent",
  },
  connecting: {
    connected: "connected",
    aura_lost: "offline_pending",
    auth_failed: "auth_failed",
    sync_failed: "auth_failed",
    internet_lost: "offline_pending",
    manual_reset: "independent",
  },
  connected: {
    aura_lost: "disconnected",
    start_delegate: "delegating",
    sync_started: "syncing",
    revoked: "revoked",
    auth_failed: "auth_failed",
    internet_lost: "offline_pending",
    offline_save: "offline_pending",
    manual_reset: "independent",
  },
  delegating: {
    delegate_complete: "connected",
    sync_started: "syncing",
    aura_lost: "disconnected",
    revoked: "revoked",
    auth_failed: "auth_failed",
    internet_lost: "offline_pending",
    offline_save: "offline_pending",
    manual_reset: "independent",
  },
  syncing: {
    sync_completed: "connected",
    sync_failed: "disconnected",
    aura_lost: "disconnected",
    revoked: "revoked",
    auth_failed: "auth_failed",
    internet_lost: "offline_pending",
    offline_save: "offline_pending",
    manual_reset: "independent",
  },
  disconnected: {
    reconnect_attempt: "reconnecting",
    aura_detected: "connecting",
    sync_started: "syncing",
    sync_failed: "auth_failed",
    revoked: "revoked",
    auth_failed: "auth_failed",
    internet_lost: "offline_pending",
    offline_save: "offline_pending",
    manual_reset: "independent",
  },
  reconnecting: {
    reconnect_success: "connected",
    aura_lost: "offline_pending",
    sync_started: "syncing",
    revoked: "revoked",
    auth_failed: "auth_failed",
    internet_lost: "offline_pending",
    offline_save: "offline_pending",
    manual_reset: "independent",
  },
  offline_pending: {
    aura_detected: "connecting",
    internet_restored: "independent",
    manual_reset: "independent",
  },
  revoked: {
    auth_restored: "discovering",
    internet_restored: "independent",
    manual_reset: "independent",
  },
  auth_failed: {
    auth_restored: "connecting",
    internet_restored: "independent",
    manual_reset: "independent",
  },
};

export type AmestatusListener = (
  state: Amestatus,
  change?: StateTransitionResult,
) => void;

export class AmestatusMachine {
  private state: Amestatus;
  private listeners = new Set<AmestatusListener>();

  constructor(initialState: Amestatus = "independent") {
    this.state = initialState;
  }

  getState(): Amestatus {
    return this.state;
  }

  canConnect(): boolean {
    return this.state === "connecting" || this.state === "connected"
      || this.state === "delegating" || this.state === "syncing"
      || this.state === "reconnecting";
  }

  canQueue(): boolean {
    return (
      this.state === "offline_pending" ||
      this.state === "disconnected" ||
      this.state === "reconnecting" ||
      this.state === "independent" ||
      this.state === "discovering" ||
      this.state === "pairing"
    );
  }

  isAuraAvailable(): boolean {
    return this.state === "connected" || this.state === "delegating"
      || this.state === "syncing" || this.state === "connecting"
      || this.state === "reconnecting";
  }

  transition(event: AmestatusEvent): StateTransitionResult | null {
    const from = this.state;
    const transitions = TRANSITIONS[from];
    const to = transitions?.[event];

    if (!to) {
      return null;
    }

    this.state = to;
    const result: StateTransitionResult = { from, to, event };

    for (const listener of this.listeners) {
      listener(this.state, result);
    }

    return result;
  }

  subscribe(listener: AmestatusListener): () => void {
    this.listeners.add(listener);
    listener(this.state);
    return () => {
      this.listeners.delete(listener);
    };
  }

  unsubscribe(listener: AmestatusListener): void {
    this.listeners.delete(listener);
  }
}

export default AmestatusMachine;
