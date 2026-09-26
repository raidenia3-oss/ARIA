"use client";

import { useEffect, useState } from "react";

interface QuakeEvent {
  id: string;
  magnitude: number;
  place: string;
  time: number;
  depth: number;
  lat: number;
  lon: number;
  distance_km?: number;
}

export default function EarthquakesPage() {
  const [events, setEvents] = useState<QuakeEvent[]>([]);
  const [risk, setRisk] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const [recentRes, riskRes] = await Promise.all([
          fetch("/api/earthquakes/recent?limit=50"),
          fetch("/api/earthquakes/risk"),
        ]);
        const recentData = await recentRes.json();
        const riskData = await riskRes.json();
        if (active) {
          setEvents(recentData.events || []);
          setRisk(riskData);
        }
      } catch {
        if (active) {
          setEvents([]);
          setRisk(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const levelColor: Record<string, string> = {
    low: "text-green-400",
    moderate: "text-yellow-400",
    high: "text-orange-400",
    critical: "text-red-500",
  };

  return (
    <div className="min-h-screen bg-[#05070a] text-gray-100 p-6">
      <h1 className="text-2xl font-bold text-[#00e5ff] mb-4">Monitoreo Sísmico</h1>

      {risk && (
        <div className="bg-[#0f1219] border border-[#7c4dff]/30 rounded p-4 mb-6">
          <h2 className="text-lg font-semibold mb-1">Riesgo actual</h2>
          <p className={`text-3xl font-bold ${levelColor[risk.level] || "text-white"}`}>
            {risk.level.toUpperCase()}
          </p>
          <p className="text-sm text-gray-400">
            Score: {risk.score.toFixed(3)} | Eventos 24h: {risk.events_24h} | Max: {risk.max_magnitude.toFixed(1)}
          </p>
          <p className="text-xs text-gray-500 mt-1">{risk.factors?.join(" | ")}</p>
        </div>
      )}

      <div className="bg-[#0f1219] border border-[#00e5ff]/30 rounded p-4">
        <h2 className="text-lg font-semibold mb-2">Eventos recientes</h2>
        {loading && <p className="text-gray-400">Cargando...</p>}
        <div className="space-y-2 max-h-[600px] overflow-y-auto">
          {events.map((ev) => (
            <div key={ev.id} className="flex justify-between border-b border-gray-700 pb-2">
              <div>
                <p className="font-mono text-sm">{ev.place}</p>
                <p className="text-xs text-gray-500">
                  {new Date(ev.time).toLocaleString()} | Prof: {ev.depth.toFixed(1)} km
                </p>
              </div>
              <div className="text-right">
                <p className="text-[#ffea00] font-bold">M {ev.magnitude.toFixed(1)}</p>
                {typeof ev.distance_km === "number" && (
                  <p className="text-xs text-gray-400">{ev.distance_km.toFixed(0)} km</p>
                )}
              </div>
            </div>
          ))}
          {!loading && !events.length && <p className="text-gray-500">Sin eventos</p>}
        </div>
      </div>
    </div>
  );
}
