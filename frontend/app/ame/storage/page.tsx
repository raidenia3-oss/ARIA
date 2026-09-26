"use client";

/**
 * /ame/storage — AME SD-Card File Manager (gestión local-first).
 *
 * Gestiona el almacenamiento del cliente AME sin depender de Termux:
 * - Estadísticas de caché local (localStorage).
 * - Exportar datos a JSON descargable (a la SD del dispositivo).
 * - Limpiar caché preservando sesión/credenciales.
 * - Ruta de descarga SD configurable y persistente.
 *
 * No accede directamente al filesystem de Android (limitación del navegador);
 * para acceso real a la SD se requiere un bridge nativo (Capacitor/TWA).
 */

import { useEffect, useState } from "react";
import { JJK } from "@/lib/jjk-theme";

const SD_PATH_KEY = "ame-sd-download-path";

interface StorageStats {
  localStorageKB: number;
  localStorageKeys: number;
  estimatedTotalKB: number;
}

function readLocalStorageStats(): { kb: number; keys: number } {
  if (typeof window === "undefined") return { kb: 0, keys: 0 };
  let bytes = 0;
  let keys = 0;
  try {
    for (let i = 0; i < window.localStorage.length; i++) {
      const k = window.localStorage.key(i);
      if (k) {
        keys += 1;
        bytes += (window.localStorage.getItem(k) || "").length + k.length;
      }
    }
  } catch {
    /* modo privado / sin acceso */
  }
  return { kb: Math.round((bytes / 1024) * 10) / 10, keys };
}

function formatBytes(kb: number): string {
  if (kb < 1024) return `${kb} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

export default function AmeStoragePage() {
  const [stats, setStats] = useState<StorageStats | null>(null);
  const [sdPath, setSdPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refreshStats = () => {
    const ls = readLocalStorageStats();
    setStats({
      localStorageKB: ls.kb,
      localStorageKeys: ls.keys,
      estimatedTotalKB: ls.kb + 512,
    });
  };

  useEffect(() => {
    refreshStats();
    setSdPath(window.localStorage.getItem(SD_PATH_KEY) || "");
  }, []);

  const handleExport = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const dump: Record<string, string | null> = {};
      for (let i = 0; i < window.localStorage.length; i++) {
        const k = window.localStorage.key(i);
        if (k) dump[k] = window.localStorage.getItem(k);
      }
      const blob = new Blob([JSON.stringify(dump, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ame-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage("✅ Datos exportados. Guarda el archivo en tu tarjeta SD.");
    } catch (err: unknown) {
      setMessage(err instanceof Error ? `Error: ${err.message}` : "Error al exportar");
    } finally {
      setBusy(false);
    }
  };

  const handleClearCache = () => {
    setBusy(true);
    setMessage(null);
    try {
      const preserve = new Set(["aura-chat-history", "aura-chat-session-id", SD_PATH_KEY]);
      const toRemove: string[] = [];
      for (let i = 0; i < window.localStorage.length; i++) {
        const k = window.localStorage.key(i);
        if (k && !preserve.has(k) && (k.startsWith("ame-") || k.startsWith("aura-"))) {
          toRemove.push(k);
        }
      }
      toRemove.forEach((k) => window.localStorage.removeItem(k));
      refreshStats();
      setMessage(`✅ Caché limpiada (${toRemove.length} claves eliminadas).`);
    } catch (err: unknown) {
      setMessage(err instanceof Error ? `Error: ${err.message}` : "Error al limpiar");
    } finally {
      setBusy(false);
    }
  };

  const handleSavePath = () => {
    window.localStorage.setItem(SD_PATH_KEY, sdPath.trim());
    setMessage(`✅ Ruta SD guardada: ${sdPath.trim() || "(por defecto)"}`);
  };

  const inputStyle = {
    background: JJK.BG,
    color: JJK.TEXT,
    borderColor: `${JJK.ACCENT}33`,
  };

  return (
    <div className="min-h-screen p-6" style={{ background: JJK.BG, color: JJK.TEXT }}>
      <div className="max-w-lg mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">💾 Almacenamiento AME</h1>
          <a href="/ame" className="text-sm" style={{ color: JJK.ACCENT2 }}>
            ← Atrás
          </a>
        </div>

        <div
          className="rounded-lg p-4 border"
          style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
        >
          <h2 className="font-bold mb-2" style={{ color: JJK.TEXT }}>
            📊 Uso de almacenamiento
          </h2>
          {stats ? (
            <ul className="text-sm space-y-1" style={{ color: `${JJK.TEXT}cc` }}>
              <li>Claves locales: {stats.localStorageKeys}</li>
              <li>Tamaño localStorage: {formatBytes(stats.localStorageKB)}</li>
              <li>Estimado total (caché): {formatBytes(stats.estimatedTotalKB)}</li>
            </ul>
          ) : (
            <p className="text-sm" style={{ color: `${JJK.TEXT}88` }}>
              Calculando…
            </p>
          )}
          <button
            onClick={refreshStats}
            className="mt-3 px-3 py-1.5 rounded text-xs"
            style={{ border: `1px solid ${JJK.ACCENT}55`, color: JJK.TEXT }}
          >
            Refrescar
          </button>
        </div>

        <div
          className="rounded-lg p-4 border space-y-3"
          style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
        >
          <h2 className="font-bold" style={{ color: JJK.TEXT }}>
            📂 Ruta de tarjeta SD
          </h2>
          <p className="text-xs" style={{ color: `${JJK.TEXT}88` }}>
            Configura la ruta de descarga para la tarjeta SD del dispositivo.
            Persistida localmente (no requiere Termux).
          </p>
          <input
            value={sdPath}
            onChange={(e) => setSdPath(e.target.value)}
            placeholder="/storage/emulated/0/Download/AURA o content://..."
            className="w-full p-2 rounded border text-sm"
            style={inputStyle}
          />
          <button
            onClick={handleSavePath}
            disabled={busy}
            className="px-3 py-1.5 rounded text-white text-sm disabled:opacity-50"
            style={{ background: JJK.ACCENT }}
          >
            Guardar ruta
          </button>
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleExport}
            disabled={busy}
            className="flex-1 py-2 rounded text-white font-semibold text-sm disabled:opacity-50"
            style={{ background: JJK.ACCENT }}
          >
            📤 Exportar datos
          </button>
          <button
            onClick={handleClearCache}
            disabled={busy}
            className="flex-1 py-2 rounded font-semibold text-sm disabled:opacity-50"
            style={{ border: `1px solid ${JJK.RED}66`, color: JJK.RED }}
          >
            🧹 Limpiar caché
          </button>
        </div>

        {message && (
          <p className="text-sm" style={{ color: JJK.ACCENT2 }}>
            {message}
          </p>
        )}

        <p className="text-xs" style={{ color: `${JJK.TEXT}66` }}>
          Nota: el acceso directo al filesystem de Android requiere un bridge
          nativo (Capacitor/TWA). Este gestor opera sobre el almacenamiento del
          navegador, disponible sin Termux.
        </p>
      </div>
    </div>
  );
}