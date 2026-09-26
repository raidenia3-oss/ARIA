import { auraService } from "./AURAService";

export interface GameState {
  connected: boolean;
  hero: {
    level: number;
    xp: number;
    xpNext: number;
    hp: number;
    maxHp: number;
    attack: number;
    defense: number;
    gold: number;
  };
  activeBuffs: Array<{
    type: string;
    value: number;
    expiresAt: number;
  }>;
  enemies: Array<{
    name: string;
    type: string;
    hp: number;
    maxHp: number;
  }>;
  recentEvents: string[];
}

export class GodotLiveService {
  private state: GameState = {
    connected: false,
    hero: {
      level: 1,
      xp: 0,
      xpNext: 100,
      hp: 100,
      maxHp: 100,
      attack: 10,
      defense: 5,
      gold: 0,
    },
    activeBuffs: [],
    enemies: [],
    recentEvents: [],
  };
  private listeners: ((state: GameState) => void)[] = [];

  constructor() {
    // Escuchar eventos del juego via AURA
    auraService.on("GODOT_STATE", (payload: any) => {
      this.state = { ...this.state, connected: true, ...payload };
      this.notify();
    });

    auraService.on("PLAYER_LEVEL_UP", (payload: any) => {
      this.state.hero = { ...this.state.hero, ...payload.stats };
      this.addEvent(`Nivel ${payload.level} alcanzado`);
      this.notify();
    });

    auraService.on("BUFF_GRANTED", (payload: any) => {
      this.state.activeBuffs.push({
        type: payload.type,
        value: payload.value,
        expiresAt: Date.now() + payload.duration * 1000,
      });
      this.addEvent(`Buff: ${payload.type} x${payload.value}`);
      this.notify();
    });

    auraService.on("ENEMY_SPAWN", (payload: any) => {
      this.state.enemies = payload.enemies || [];
      this.addEvent(`${payload.enemies?.length || 0} enemigos spawneados`);
      this.notify();
    });

    auraService.on("AURA_DISCONNECTED", () => {
      this.state.connected = false;
      this.notify();
    });

    // Limpiar buffs expirados cada 10s
    setInterval(() => {
      const now = Date.now();
      const before = this.state.activeBuffs.length;
      this.state.activeBuffs = this.state.activeBuffs.filter(
        (b) => b.expiresAt > now,
      );
      if (this.state.activeBuffs.length !== before) this.notify();
    }, 10000);

    // Pedir estado del juego al conectar
    auraService.on("connection", () => {
      auraService.send("GODOT_GET_STATE", {});
    });
  }

  // Dar XP manualmente (debug/admin)
  grantXP(amount: number): void {
    auraService.send("GODOT_REMOTE_CMD", {
      command: "GRANT_XP",
      args: { amount },
    });
  }

  // Pausar/reanudar el juego
  togglePause(): void {
    auraService.send("GODOT_REMOTE_CMD", { command: "TOGGLE_PAUSE" });
  }

  // Forzar spawn de enemigo
  forceEnemySpawn(type = "MINION"): void {
    auraService.send("GODOT_REMOTE_CMD", {
      command: "FORCE_SPAWN",
      args: { type },
    });
  }

  getState(): GameState {
    return this.state;
  }

  onChange(cb: (state: GameState) => void): void {
    this.listeners.push(cb);
    cb(this.state);
  }

  private addEvent(msg: string): void {
    const time = new Date().toLocaleTimeString("es", {
      hour: "2-digit",
      minute: "2-digit",
    });
    this.state.recentEvents.unshift(`${time} ${msg}`);
    this.state.recentEvents = this.state.recentEvents.slice(0, 20);
  }

  private notify(): void {
    this.listeners.forEach((cb) => cb(this.state));
  }
}

export const godotLiveService = new GodotLiveService();
