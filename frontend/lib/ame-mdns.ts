"use client";

/**
 * AME mDNS / Auto-Discovery Hook (BLOQUE 35).
 *
 * En entornos donde el cliente web no puede usar mDNS de forma nativa (no hay
 * API mDNS en browsers estándar), este módulo implementa un escaneo ligero de
 * subred local + fallback manual para localizar el host AURA.
 *
 * Estrategia:
 * 1. Si existe un host manual guardado en localStorage (AURA_MANUAL_HOST), usarlo.
 * 2. Escanear IPs de la subred local del cliente (obtenida vía WebRTC trick).
 * 3. Escanear subredes comunes (192.168.0.x, 192.168.1.x, 10.0.0.x).
 * 4. Para cada candidato, hacer un ping REST a /api/mobile/discovery.
 *
 * Variables de entorno / localStorage:
 * - NEXT_PUBLIC_AURA_BACKEND_URL — backend por defecto (localhost:8000).
 * - AURA_MANUAL_HOST — IP/host manual para fallback (p. ej. Tailscale).
 * - AURA_DISCOVERY_PORT — puerto a escanear (default: 8000).
 */

export interface AuraHost {
  host: string;
  port: number;
  name: string;
  baseUrl: string;
  source: "manual" | "network" | "default";
}

export const DEFAULT_DISCOVERY_PORT = Number(
  process.env.NEXT_PUBLIC_AURA_DISCOVERY_PORT || "8000",
);
const DISCOVERY_TIMEOUT_MS = 1500;
export const MANUAL_HOST_KEY = "AURA_MANUAL_HOST";
export const SAVED_HOST_KEY = "AURA_SAVED_HOST";

const DEFAULT_SUBNETS = ["192.168.0", "192.168.1", "10.0.0", "10.0.1", "172.16.0"];

function isAuraHost(data: unknown): data is { name: string; port?: number } {
  return typeof data === "object" && data !== null && (data as any).name?.includes?.("AURA");
}

export async function pingAuraHost(
  baseUrl: string,
  timeoutMs: number = DISCOVERY_TIMEOUT_MS,
): Promise<AuraHost | null> {
  try {
    const res = await fetch(`${baseUrl}/api/mobile/discovery`, {
      method: "GET",
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) return null;
    const data = await res.json().catch(() => null);
    if (isAuraHost(data)) {
      return {
        host: baseUrl.replace(/^https?:\/\//, "").replace(/\/$/, ""),
        port: Number(data.port) || DEFAULT_DISCOVERY_PORT,
        name: data.name as string,
        baseUrl,
        source: "network",
      };
    }
  } catch {
    // Silencioso: candidato no responde.
  }
  return null;
}

export function tryManualHost(): AuraHost | null {
  if (typeof window === "undefined") return null;
  const manual = localStorage.getItem(MANUAL_HOST_KEY)?.trim() || "";
  if (!manual) return null;
  const base = manual.startsWith("http") ? manual : `http://${manual}`;
  return {
    host: manual,
    port: DEFAULT_DISCOVERY_PORT,
    name: "AURA OS (Manual)",
    baseUrl: base,
    source: "manual",
  };
}

export function saveManualHost(host: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(MANUAL_HOST_KEY, host.trim());
  localStorage.setItem(SAVED_HOST_KEY, host.trim());
}

export function clearManualHost(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(MANUAL_HOST_KEY);
}

export function getSavedHost(): AuraHost | null {
  if (typeof window === "undefined") return null;
  const saved = localStorage.getItem(SAVED_HOST_KEY)?.trim() || "";
  if (!saved) return null;
  const base = saved.startsWith("http") ? saved : `http://${saved}`;
  return {
    host: saved,
    port: DEFAULT_DISCOVERY_PORT,
    name: "AURA OS",
    baseUrl: base,
    source: "network",
  };
}

export function saveDiscoveredHost(baseUrl: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(SAVED_HOST_KEY, baseUrl);
}

export async function getClientIPs(): Promise<string[]> {
  const ips: Set<string> = new Set();
  try {
    const pc = new RTCPeerConnection({ iceServers: [] }) as any;
    pc.createDataChannel("");
    pc.createOffer({ iceRestart: true }).then((offer: RTCSessionDescriptionInit) => {
      pc.setLocalDescription(offer);
    });
    await new Promise<void>((resolve) => {
      pc.onicecandidate = (e: any) => {
        if (e && e.candidate && e.candidate.candidate) {
          const m = /(\d+\.\d+\.\d+\.\d+)/.exec(e.candidate.candidate);
          if (m && m[1]) ips.add(m[1]);
        }
      };
      setTimeout(() => {
        pc.close();
        resolve();
      }, 500);
    });
  } catch {
    // WebRTC no disponible → devolver subredes comunes.
  }
  return Array.from(ips);
}

export function generateCandidateHosts(clientIP: string | null): string[] {
  const subnets: Set<string> = new Set();
  if (clientIP && /^\d+\.\d+\.\d+\.\d+$/.test(clientIP)) {
    const parts = clientIP.split(".");
    subnets.add(`${parts[0]}.${parts[1]}.${parts[2]}`);
  }
  for (const s of DEFAULT_SUBNETS) subnets.add(s);

  const ports = [DEFAULT_DISCOVERY_PORT];
  const hosts: string[] = [];
  for (const subnet of subnets) {
    for (let i = 1; i <= 254; i++) {
      const ip = `${subnet}.${i}`;
      for (const port of ports) {
        hosts.push(`http://${ip}:${port}`);
      }
    }
  }
  return hosts;
}

export async function discoverAuraHosts(
  timeoutMs: number = DISCOVERY_TIMEOUT_MS,
  maxCandidates: number = 60,
): Promise<AuraHost[]> {
  const saved = getSavedHost();
  if (saved) {
    const host = await pingAuraHost(saved.baseUrl, timeoutMs);
    if (host) return [host];
  }

  const clientIP = await getClientIPs().then((ips) => ips.find((ip) => !ip.startsWith("127.")) || null);
  const candidates = generateCandidateHosts(clientIP);
  const found: AuraHost[] = [];

  const batch = candidates.slice(0, maxCandidates);
  await Promise.all(
    batch.map(async (baseUrl) => {
      const host = await pingAuraHost(baseUrl, timeoutMs);
      if (host) found.push(host);
    }),
  );

  if (found.length > 0) {
    saveDiscoveredHost(found[0].baseUrl);
  }
  return found;
}

export async function discoverAuraHost(preferredFirst: string | null = null): Promise<AuraHost | null> {
  const manual = tryManualHost();
  if (manual) return manual;

  if (preferredFirst) {
    const host = await pingAuraHost(preferredFirst);
    if (host) return host;
  }

  const hosts = await discoverAuraHosts();
  return hosts[0] || null;
}
