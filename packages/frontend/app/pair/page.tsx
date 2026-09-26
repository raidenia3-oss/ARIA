"use client";

/**
 * /pair — Asistente de vinculación LAN (AURA HOST ⇄ AME CLIENT).
 *
 * 1. El usuario introduce la URL base del host (o el payload del QR).
 * 2. El asistente obtiene el perfil de emparejamiento (código + token efímero).
 * 3. Canjea el código vía /api/mobile/pairing/handshake y persiste
 *    la URL del host y el token de dispositivo en localStorage.
 *
 * El token del dispositivo se guarda solo en localStorage del cliente;
 * nunca se envía a terceros ni se loguea.
 */

import { useEffect, useState } from "react";
import { JJK } from "@/lib/jjk-theme";

const HOST_KEY = "aura-paired-host";
const TOKEN_KEY = "aura-paired-device-token";
const DEVICE_KEY = "aura-paired-device-id";

interface PairingProfile {
  host_ip: string;
  port: number;
  backend_url: string;
  code: string;
  token: string;
  expires_at: number;
  ttl_seconds: number;
  qr_payload: string;
}

interface PairResult {
  status: string;
  device_id: string;
  device_token: string;
  backend_url: string;
}

type Stage = "input" | "profile" | "paired";

export default function PairPage() {
  const [hostInput, setHostInput] = useState("");
  const [qrPayload, setQrPayload] = useState("");
  const [profile, setProfile] = useState<PairingProfile | null>(null);
  const [result, setResult] = useState<PairResult | null>(null);
  const [stage, setStage] = useState<Stage>("input");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pairedHost, setPairedHost] = useState<string | null>(null);
  const [pingMs, setPingMs] = useState<number | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem(HOST_KEY);
    if (saved) {
      setPairedHost(saved);
      setStage("paired");
    }
  }, []);

  const normalizeHost = (raw: string): string => {
    const value = raw.trim();
    if (!value) return "";
    if (/^https?:\/\//i.test(value)) return value.replace(/\/$/, "");
    if (/^\d{6}$/.test(value)) return ""; // código suelto no es una URL
    return `http://${value.replace(/\/$/, "")}`;
  };

  const fetchProfile = async () => {
    const host = normalizeHost(hostInput);
    if (!host || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${host}/api/mobile/pairing/profile`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setProfile((await res.json()) as PairingProfile);
      setStage("profile");
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? `No se pudo contactar al host: ${err.message}`
          : "Error de red"
      );
    } finally {
      setBusy(false);
    }
  };

  const completePairing = async () => {
    if (!profile || busy) return;
    setBusy(true);
    setError(null);
    try {
      const deviceId = localStorage.getItem(DEVICE_KEY) || `ame_${Date.now()}`;
      const res = await fetch(`${profile.backend_url}/api/mobile/pairing/handshake`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          qr_payload: profile.qr_payload,
          code: profile.code,
          token: profile.token,
          device_id: deviceId,
          device_name: "AME Mobile",
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = (await res.json()) as PairResult;
      localStorage.setItem(HOST_KEY, profile.backend_url);
      localStorage.setItem(TOKEN_KEY, body.device_token);
      localStorage.setItem(DEVICE_KEY, body.device_id);
      setResult(body);
      setPairedHost(profile.backend_url);
      setStage("paired");
    } catch (err: unknown) {
      setError(err instanceof Error ? `Handshake falló: ${err.message}` : "Error");
    } finally {
      setBusy(false);
    }
  };

  const measureLatency = async () => {
    const host = pairedHost || profile?.backend_url;
    if (!host) return;
    setBusy(true);
    try {
      const start = performance.now();
      await fetch(`${host}/api/mobile/pairing/ping`);
      setPingMs(Math.round(performance.now() - start));
    } catch {
      setPingMs(null);
    } finally {
      setBusy(false);
    }
  };

    const inputStyle = {
    background: JJK.BG,
    color: JJK.TEXT,
    borderColor: `${JJK.ACCENT}33`,
  };

  return (
    <div className="min-h-screen p-6" style={{ background: JJK.BG, color: JJK.TEXT }}>
      <div className="max-w-md mx-auto space-y-4">
        <h1 className="text-xl font-bold">🔗 Emparejar con AURA HOST</h1>

        {stage === "paired" && (
          <div
            className="rounded-lg p-4 border text-sm space-y-2"
            style={{
              borderColor: `${JJK.ACCENT2}66`,
              background: `${JJK.ACCENT2}11`,
            }}
          >
            <p>✅ Emparejado con:</p>
            <p className="font-mono font-bold">{pairedHost}</p>
            <button
              onClick={measureLatency}
              disabled={busy}
              className="mt-2 px-3 py-1.5 rounded text-xs disabled:opacity-50"
              style={{ border: `1px solid ${JJK.ACCENT}55` }}
            >
              {pingMs === null ? "Medir latencia" : `Latencia: ${pingMs} ms`}
            </button>
          </div>
        )}

        {stage !== "paired" && (
          <div
            className="rounded-lg p-4 border space-y-3"
            style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
          >
            <input
              value={hostInput}
              onChange={(e) => setHostInput(e.target.value)}
              placeholder="URL del host (ej. 192.168.1.50:8000)"
              className="w-full p-2 rounded border text-sm"
              style={inputStyle}
            />
            <button
              onClick={fetchProfile}
              disabled={busy || !hostInput.trim()}
              className="w-full py-2 rounded text-white font-semibold text-sm disabled:opacity-50"
              style={{ background: JJK.ACCENT }}
            >
              {busy ? "…" : "1. Obtener perfil de emparejamiento"}
            </button>
          </div>
        )}

        {stage === "profile" && profile && (
          <div
            className="rounded-lg p-4 border space-y-3 text-sm"
            style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
          >
            <p>
              Host: <strong>{profile.host_ip}:{profile.port}</strong>
            </p>
            <p>
              Código de emparejamiento:{" "}
              <span
                className="font-mono font-bold text-lg tracking-widest px-2 py-1 rounded"
                style={{ background: `${JJK.ACCENT}22`, color: JJK.ACCENT2 }}
              >
                {profile.code}
              </span>
            </p>
            <p className="text-xs" style={{ color: `${JJK.TEXT}77` }}>
              Expira en {profile.ttl_seconds}s. Un solo uso.
            </p>
            <button
              onClick={completePairing}
              disabled={busy}
              className="w-full py-2 rounded text-white font-semibold text-sm disabled:opacity-50"
              style={{ background: JJK.ACCENT }}
            >
              {busy ? "…" : "2. Completar emparejamiento"}
            </button>
          </div>
        )}

        {result && (
          <div className="text-xs" style={{ color: JJK.ACCENT2 }}>
            Device ID: <span className="font-mono">{result.device_id}</span>
          </div>
        )}

        {error && (
          <p className="text-sm" style={{ color: JJK.RED }}>
            ⚠ {error}
          </p>
        )}
      </div>
    </div>
  );
}