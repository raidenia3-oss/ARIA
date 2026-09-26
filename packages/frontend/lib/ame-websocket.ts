"use client";

import { SyncEvent, toWireFormat, parseIncomingMessage, createEvent } from "./ame-events";
import type { AmestatusMachine } from "./ame-state-machine";

const DEFAULT_BACKEND = "http://localhost:8000";
const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 32000;
const MAX_RETRIES = 8;

export interface WebSocketMessage {
  eventId: string;
  deviceId: string;
  type: string;
  createdAt: string;
  schemaVersion: number;
  payload: Record<string, unknown>;
}

export type AmewebSocketStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "error"
  | "max_retries_exceeded";

export interface AmewebSocketConfig {
  backendUrl?: string;
  deviceId: string;
  authToken?: string;
  streamEndpoint?: string;
  onOpen?: () => void;
  onAuthenticated?: () => void;
  onClose?: (clean: boolean) => void;
  onError?: (err: Error) => void;
  onMessage?: (msg: WebSocketMessage) => void;
  onStatusChange?: (status: AmewebSocketStatus) => void;
}

export class AmewebSocketClient {
  private config: AmewebSocketConfig;
  private stateMachine: AmestatusMachine | null = null;
  private ws: WebSocket | null = null;
  private status: AmewebSocketStatus = "disconnected";
  private retryCount = 0;
  private backoffTimer: ReturnType<typeof setTimeout> | null = null;
  private currentBackoff = INITIAL_BACKOFF_MS;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private destroyed = false;
  private authenticated = false;
  private closeTimeout: ReturnType<typeof setTimeout> | null = null;
  private onCloseHandled = false;
  private connectTimeout: ReturnType<typeof setTimeout> | null = null;
  private static readonly CONNECT_TIMEOUT_MS = 5000;

  constructor(config: AmewebSocketConfig) {
    this.config = config;
  }

  setStateMachine(machine: AmestatusMachine): void {
    this.stateMachine = machine;
  }

  private getWebSocketUrl(): string {
    const base = this.config.backendUrl || DEFAULT_BACKEND;
    const wsProto = base.startsWith("https") ? "wss" : "ws";
    const normalized = base.replace(/^https?:\/\//, "");
    const endpoint = this.config.streamEndpoint === "stream"
      ? "/api/ws/stream"
      : `/api/mobile/sync/${this.config.deviceId}`;
    return `${wsProto}://${normalized}${endpoint}`;
  }

  private setConnectionStatus(status: AmewebSocketStatus): void {
    if (this.status === status && this.status !== "connected") return;
    this.status = status;
    this.config.onStatusChange?.(status);

    if (this.stateMachine) {
      switch (status) {
        case "connected":
          this.stateMachine.transition("connected");
          break;
        case "disconnected":
          if (this.retryCount >= MAX_RETRIES) {
            this.stateMachine.transition("auth_failed");
          } else {
            this.stateMachine.transition("aura_lost");
            this.stateMachine.transition("reconnect_attempt");
          }
          break;
        case "connecting":
          this.stateMachine.transition("reconnect_attempt");
          break;
        case "max_retries_exceeded":
          this.stateMachine.transition("sync_failed");
          break;
        case "error":
          this.stateMachine.transition("sync_failed");
          break;
      }
    }
  }

  connect(): void {
    if (this.destroyed || this.ws) return;

    this.setConnectionStatus("connecting");
    this.retryCount = 0;
    this.currentBackoff = INITIAL_BACKOFF_MS;
    this.onCloseHandled = false;
    if (this.closeTimeout) {
      clearTimeout(this.closeTimeout);
      this.closeTimeout = null;
    }

    const url = this.getWebSocketUrl();
    this.ws = new WebSocket(url);

    this.connectTimeout = setTimeout(() => {
      if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
       this.ws.close();
      }
    }, AmewebSocketClient.CONNECT_TIMEOUT_MS);

    this.ws.onopen = () => {
      if (this.connectTimeout) {
        clearTimeout(this.connectTimeout);
        this.connectTimeout = null;
      }
      this.retryCount = 0;
      this.currentBackoff = INITIAL_BACKOFF_MS;
      this.startPing();
      this.authenticated = false;
      const authMsg: Record<string, unknown> = {
        type: "auth",
        token: this.config.authToken ?? "",
      };
      if (this.config.deviceId) {
        authMsg.deviceId = this.config.deviceId;
      }
      this.ws?.send(JSON.stringify(authMsg));
    };

    this.ws.onmessage = (ev: MessageEvent<string>) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg?.status === "ok" && (msg?.auth === "accepted" || msg?.auth === "ok")) {
          this.authenticated = true;
          this.setConnectionStatus("connected");
          this.config.onOpen?.();
          this.config.onAuthenticated?.();
          return;
        }
        if (msg?.status === "error" && (msg?.auth === "auth_failed" || msg?.auth === "invalid_token")) {
          this.setConnectionStatus("error");
          this.config.onError?.(new Error("Authentication failed"));
          this.ws?.close();
          return;
        }
        const event = parseIncomingMessage(msg);

        if (event) {
          this.config.onMessage?.({
            eventId: event.eventId,
            deviceId: event.deviceId,
            type: event.type,
            createdAt: event.createdAt,
            schemaVersion: event.schemaVersion,
            payload: event.payload,
          });
        } else {
          this.config.onMessage?.(msg as WebSocketMessage);
        }
      } catch (err) {
        this.config.onError?.(err instanceof Error ? err : new Error(String(err)));
      }
    };

    this.ws.onerror = () => {
      this.setConnectionStatus("error");
      this.config.onError?.(new Error("WebSocket connection error"));
      if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close();
      }
      if (!this.destroyed && !this.closeTimeout) {
        this.closeTimeout = setTimeout(() => {
          this.handleClose({} as CloseEvent);
        }, 1500);
      }
    };

    this.ws.onclose = (ev: CloseEvent) => {
      this.handleClose(ev);
    };
  }

   private handleClose(ev: CloseEvent): void {
    if (this.onCloseHandled) return;
    this.onCloseHandled = true;
    if (this.closeTimeout) {
      clearTimeout(this.closeTimeout);
      this.closeTimeout = null;
    }
    if (this.connectTimeout) {
      clearTimeout(this.connectTimeout);
      this.connectTimeout = null;
    }

    this.stopPing();
    this.ws = null;
    this.authenticated = false;

    if (this.destroyed) return;

    this.retryCount++;

    if (this.retryCount > MAX_RETRIES) {
      this.setConnectionStatus("max_retries_exceeded");
      this.config.onClose?.(false);
      return;
    }

    this.setConnectionStatus("disconnected");
    this.config.onClose?.(ev.wasClean);

    this.backoffTimer = setTimeout(() => {
      this.connect();
    }, this.currentBackoff);

    this.currentBackoff = Math.min(this.currentBackoff * 2, MAX_BACKOFF_MS);
  }

  send(event: SyncEvent): void {
    if (this.authenticated && this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(toWireFormat(event)));
      return;
    }

    if (this.stateMachine) {
      this.stateMachine.transition("offline_save");
    }
  }

  subscribe(workId: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "subscribe", work_id: workId }));
    }
  }

  private startPing(): void {
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(
          JSON.stringify(
            toWireFormat(
              createEvent(
                "status_update",
                { action: "ping" },
                this.config.deviceId,
              ),
            ),
          ),
        );
      }
    }, 30000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  disconnect(): void {
    this.destroyed = true;
    this.stopPing();

    if (this.backoffTimer) {
      clearTimeout(this.backoffTimer);
      this.backoffTimer = null;
    }

    if (this.closeTimeout) {
      clearTimeout(this.closeTimeout);
      this.closeTimeout = null;
    }

    if (this.connectTimeout) {
      clearTimeout(this.connectTimeout);
      this.connectTimeout = null;
    }

    if (this.ws) {
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.close();
      this.ws = null;
    }

    this.setConnectionStatus("disconnected");
    this.authenticated = false;
  }

  getStatus(): AmewebSocketStatus {
    return this.status;
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  getRetryCount(): number {
    return this.retryCount;
  }
}

export default AmewebSocketClient;
