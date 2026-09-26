"use client";

import { useEffect, useRef, useState } from "react";

interface Network {
  ssid: string;
  bssid: string;
  rssi: number;
  channel: number;
  frequency: number;
  timestamp: number;
}

export default function WifiRadarPage() {
  const [networks, setNetworks] = useState<Network[]>([]);
  const [motion, setMotion] = useState<any[]>([]);
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [zones, setZones] = useState<any[]>([]);
  const [scanning, setScanning] = useState(false);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const startScan = () => {
    setScanning(true);
    intervalRef.current = window.setInterval(async () => {
      try {
        const res = await fetch("/api/wifi/stream");
        const data = await res.json();
        setNetworks(data.networks || []);
        setZones(data.zones || []);
        setMotion(data.motion || []);
        setAnomalies(data.anomalies || []);
      } catch {
        setNetworks([]);
        setZones([]);
        setMotion([]);
        setAnomalies([]);
      }
    }, 1000);
  };

  const stopScan = () => {
    setScanning(false);
    if (intervalRef.current) clearInterval(intervalRef.current);
  };

  return (
    <div className="min-h-screen bg-[#05070a] text-gray-100 p-6">
      <h1 className="text-2xl font-bold text-[#00e5ff] mb-4">WiFi Radar</h1>
      <div className="flex gap-2 mb-6">
        <button
          onClick={startScan}
          disabled={scanning}
          className="px-4 py-2 bg-[#7c4dff] hover:bg-[#7c4dff]/80 rounded disabled:opacity-50"
        >
          {scanning ? "Escaneando..." : "Iniciar escaneo"}
        </button>
        <button
          onClick={stopScan}
          disabled={!scanning}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded disabled:opacity-50"
        >
          Detener
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-[#0f1219] border border-[#00e5ff]/30 rounded p-4">
          <h2 className="text-lg font-semibold mb-2">Mapa de presencia</h2>
          <div className="relative w-full h-96 bg-black/40 rounded">
            {zones.map((z, i) => (
              <div
                key={i}
                className="absolute rounded-full bg-[#7c4dff]"
                style={{
                  left: `${z.x * 100}%`,
                  top: `${z.y * 100}%`,
                  width: `${20 + z.intensity * 40}px`,
                  height: `${20 + z.intensity * 40}px`,
                  opacity: 0.6 + z.intensity * 0.4,
                }}
                title={z.label}
              />
            ))}
          </div>
        </div>

        <div className="bg-[#0f1219] border border-[#7c4dff]/30 rounded p-4">
          <h2 className="text-lg font-semibold mb-2">Redes detectadas</h2>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {networks.map((n, i) => (
              <div key={i} className="flex justify-between border-b border-gray-700 pb-1">
                <span className="truncate">{n.ssid || n.bssid}</span>
                <span className="text-[#00e5ff]">{n.rssi} dBm</span>
              </div>
            ))}
            {!networks.length && <p className="text-gray-500">Sin datos</p>}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <div className="bg-[#0f1219] border border-[#ff4d4d]/30 rounded p-4">
          <h2 className="text-lg font-semibold mb-2">Movimiento</h2>
          <pre className="text-xs text-gray-300">{JSON.stringify(motion, null, 2)}</pre>
        </div>
        <div className="bg-[#0f1219] border border-[#ffea00]/30 rounded p-4">
          <h2 className="text-lg font-semibold mb-2">Anomalías</h2>
          <pre className="text-xs text-gray-300">{JSON.stringify(anomalies, null, 2)}</pre>
        </div>
      </div>
    </div>
  );
}
