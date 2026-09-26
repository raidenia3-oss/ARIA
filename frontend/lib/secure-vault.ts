"use client";

/**
 * AME SD-Card Secure Vault (Bloque 36, funcionalidad 2).
 *
 * Bóveda cifrada at-rest para buffers guardados en la tarjeta SD externa del
 * móvil. Si se extrae el medio físico, los datos son ilegibles sin la clave
 * de sesión derivada del secreto maestro del escritor.
 *
 * Diseño local-first (sin dependencias externas):
 * - Cifrado: WebCrypto AES-256-GCM (autenticado) con IV aleatorio por buffer.
 * - Derivación de llave: PBKDF2-HMAC-SHA256 (310k iteraciones) desde el secreto
 *   maestro del usuario. La clave NUNCA se persiste: solo vive en memoria
 *   (CryptoKey no extraíble) mientras la sesión está abierta.
 * - Session Lock: la bóveda se bloquea automáticamente tras un periodo de
 *   inactividad (configurable, default 15 min).
 * - Formato en SD: JSON { magic, iv, data, createdAt } en base64url.
 */

const MAGIC = "AMEVAULT1";
const PBKDF2_ITERATIONS = 310_000;
const DEFAULT_LOCK_SECS = 900; // 15 minutos de inactividad.

export interface SecureVaultConfig {
  /** Directorio lógico de la tarjeta SD (el caller persiste los blobs). */
  storageDir?: string;
  /** Segundos de inactividad antes del auto-lock. */
  lockSecs?: number;
  /** Callback opcional al cambiar de estado locked/unlocked. */
  onLockChange?: (locked: boolean) => void;
}

export interface VaultBlob {
  magic: string;
  iv: string;
  data: string;
  createdAt: number;
}

export type VaultWriter = (name: string, blob: string) => Promise<void>;
export type VaultReader = (name: string) => Promise<string | null>;

export interface SecureVaultStatus {
  locked: boolean;
  lockSecs: number;
  secondsUntilLock: number;
  entries: number;
}

function toBase64Url(bytes: Uint8Array): string {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(text: string): Uint8Array {
  const b64 = text.replace(/-/g, "+").replace(/_/g, "/");
  const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
  const bin = atob(padded);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function deriveCryptoKey(
  masterSecret: string,
  salt: Uint8Array,
): Promise<CryptoKey> {
  const enc = new TextEncoder();
  const baseKey = await crypto.subtle.importKey(
    "raw",
    enc.encode(masterSecret),
    "PBKDF2",
    false,
    ["deriveKey"],
  );
  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: salt as unknown as BufferSource,
      iterations: PBKDF2_ITERATIONS,
      hash: "SHA-256",
    },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false, // no extraíble: la clave no sale de memoria en claro
    ["encrypt", "decrypt"],
  );
}

export class SecureVault {
  private cryptoKey: CryptoKey | null = null;
  private lastActivity = 0;
  private readonly lockSecs: number;
  private readonly onLockChange?: (locked: boolean) => void;
  private entries = new Set<string>();

  constructor(private readonly config: SecureVaultConfig = {}) {
    this.lockSecs = config.lockSecs ?? DEFAULT_LOCK_SECS;
    this.onLockChange = config.onLockChange;
  }

  /** Estado del session lock (sin exponer secretos). */
  get isLocked(): boolean {
    return this.cryptoKey === null;
  }

  get secondsUntilLock(): number {
    if (this.isLocked) return 0;
    return Math.max(
      0,
      this.lockSecs - Math.floor((Date.now() - this.lastActivity) / 1000),
    );
  }

  /** Abre la sesión: deriva la clave en memoria (no se persiste). */
  async unlock(masterSecret: string): Promise<void> {
    if (!masterSecret) {
      throw new Error("master secret requerido para desbloquear la bóveda");
    }
    const salt = crypto.getRandomValues(new Uint8Array(16));
    this.cryptoKey = await deriveCryptoKey(masterSecret, salt);
    this.lastActivity = Date.now();
    this.onLockChange?.(false);
  }

  /** Cierra la sesión: borra la clave de memoria. */
  lock(): void {
    this.cryptoKey = null;
    this.lastActivity = 0;
    this.onLockChange?.(true);
  }

  /** Bloquea si se superó el periodo de inactividad. */
  autoLockIfIdle(): void {
    if (!this.isLocked && this.secondsUntilLock <= 0) this.lock();
  }

  private requireKey(): CryptoKey {
    this.autoLockIfIdle();
    if (!this.cryptoKey) {
      throw new Error("bóveda bloqueada: se requiere unlock(masterSecret)");
    }
    this.lastActivity = Date.now();
    return this.cryptoKey;
  }

  /**
   * Cifra un buffer (texto serializable) para guardarlo en la SD.
   * Retorna el blob cifrado listo para que el caller lo escriba al medio.
   */
  async encryptBuffer(payload: string): Promise<string> {
    const key = this.requireKey();
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const enc = new TextEncoder();
    const cipher = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: iv as unknown as BufferSource },
      key,
      enc.encode(payload),
    );
    const blob: VaultBlob = {
      magic: MAGIC,
      iv: toBase64Url(iv),
      data: toBase64Url(new Uint8Array(cipher)),
      createdAt: Date.now(),
    };
    return JSON.stringify(blob);
  }

  /** Descifra un blob previamente cifrado con encryptBuffer. */
  async decryptBuffer(blobJson: string): Promise<string> {
    const key = this.requireKey();
    let parsed: VaultBlob;
    try {
      parsed = JSON.parse(blobJson) as VaultBlob;
    } catch {
      throw new Error("blob de bóveda corrupto");
    }
    if (parsed.magic !== MAGIC) {
      throw new Error("magic de bóveda no reconocido");
    }
    const iv = fromBase64Url(parsed.iv);
    const data = fromBase64Url(parsed.data);
    const plain = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: iv as unknown as BufferSource },
      key,
      data as unknown as BufferSource,
    );
    return new TextDecoder().decode(plain);
  }

  /**
   * Guarda un buffer cifrado en la tarjeta SD a través de writers inyectados
   * (adaptador de almacenamiento del móvil). El caller decide el mecanismo
   * físico (SAF/FileSystem Access/RNFS); aquí solo se cifra y se registra.
   */
  async saveToStorage(
    name: string,
    payload: string,
    writer: VaultWriter,
  ): Promise<void> {
    const blob = await this.encryptBuffer(payload);
    await writer(name, blob);
    this.entries.add(name);
  }

  /** Lee un blob cifrado desde la SD y lo descifra en memoria. */
  async readFromStorage(
    name: string,
    reader: VaultReader,
  ): Promise<string | null> {
    const blobJson = await reader(name);
    if (!blobJson) return null;
    this.entries.add(name);
    return this.decryptBuffer(blobJson);
  }

  status(): SecureVaultStatus {
    return {
      locked: this.isLocked,
      lockSecs: this.lockSecs,
      secondsUntilLock: this.secondsUntilLock,
      entries: this.entries.size,
    };
  }
}

export default SecureVault;