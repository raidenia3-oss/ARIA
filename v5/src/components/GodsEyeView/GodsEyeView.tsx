import { useEffect, useRef, useState } from 'react'

export interface GeoPoint {
  id: string
  name: string
  lat: number
  lng: number
  type: 'traffic' | 'fleet' | 'satellite' | 'infrastructure'
  status: 'active' | 'idle' | 'error'
  metadata?: Record<string, unknown>
}

export interface GodsEyeState {
  points: GeoPoint[]
  selectedPoint: GeoPoint | null
  zoom: number
  center: [number, number]
}

const TYPE_COLORS: Record<GeoPoint['type'], string> = {
  traffic: '#34d399',
  fleet: '#38bdf8',
  satellite: '#a78bfa',
  infrastructure: '#f59e0b',
}

function useGeospatial(poll_ms = 5000): { points: GeoPoint[] } {
  const [points, setPoints] = useState<GeoPoint[]>([])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch('/api/agents/geospatial/status')
        const data = await res.json()
        if (cancelled) return
        setPoints((data.points || []).map((p: Record<string, unknown>) => ({
          id: String(p.id || ''),
          name: String(p.name || ''),
          lat: Number(p.lat || 0),
          lng: Number(p.lng || 0),
          type: (p.type as GeoPoint['type']) || 'traffic',
          status: (p.status as GeoPoint['status']) || 'active',
          metadata: p.metadata as Record<string, unknown> | undefined,
        })))
      } catch {
        /* backend no disponible */
      }
    }
    load()
    const id = setInterval(load, poll_ms)
    return () => { cancelled = true; clearInterval(id) }
  }, [poll_ms])
  return { points }
}

function latLngToXY(lat: number, lng: number, width: number, height: number, center: [number, number], zoom: number): [number, number] {
  const scale = Math.pow(2, zoom) * 100
  const x = width / 2 + (lng - center[1]) * scale / 100
  const y = height / 2 - (lat - center[0]) * scale / 100
  return [x, y]
}

export function GodsEyeView() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { points } = useGeospatial()
  const [zoom, setZoom] = useState(3)
  const [center, setCenter] = useState<[number, number]>([0, 0])
  const [selectedPoint, setSelectedPoint] = useState<GeoPoint | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)

    const W = rect.width
    const H = rect.height

    // Dark background
    ctx.fillStyle = '#0f172a'
    ctx.fillRect(0, 0, W, H)

    // Grid
    ctx.strokeStyle = '#1e293b'
    ctx.lineWidth = 0.5
    const gridSize = 40 * Math.pow(2, zoom) / 4
    for (let x = 0; x < W; x += gridSize) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
    }
    for (let y = 0; y < H; y += gridSize) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
    }

    // Draw points
    points.forEach((p) => {
      const [x, y] = latLngToXY(p.lat, p.lng, W, H, center, zoom)
      if (x < -50 || x > W + 50 || y < -50 || y > H + 50) return

      const color = TYPE_COLORS[p.type]
      const r = p.status === 'active' ? 6 : 4

      // Glow
      ctx.shadowColor = color
      ctx.shadowBlur = p.status === 'active' ? 15 : 5
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.arc(x, y, r, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0

      // Label
      ctx.fillStyle = '#e2e8f0'
      ctx.font = '10px monospace'
      ctx.fillText(p.name, x + 8, y + 3)
    })

    // Center crosshair
    ctx.strokeStyle = '#38bdf8'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(W / 2 - 10, H / 2)
    ctx.lineTo(W / 2 + 10, H / 2)
    ctx.moveTo(W / 2, H / 2 - 10)
    ctx.lineTo(W / 2, H / 2 + 10)
    ctx.stroke()
  }, [points, zoom, center])

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault()
    const newZoom = Math.max(1, Math.min(18, zoom - e.deltaY * 0.001))
    setZoom(newZoom)
  }

  return (
    <div className="relative h-full w-full">
      <canvas
        ref={canvasRef}
        className="h-full w-full cursor-grab"
        onWheel={handleWheel}
      />
      <div className="absolute left-2 top-2 rounded bg-black/50 px-2 py-1 text-[10px] font-mono text-cyan-400">
        ZOOM {zoom.toFixed(1)} · {points.length} POINTS
      </div>
      {selectedPoint && (
        <div className="absolute right-2 top-2 w-56 rounded bg-black/70 p-2 text-[10px] font-mono">
          <div className="text-cyan-400">{selectedPoint.name}</div>
          <div className="text-gray-400">Type: {selectedPoint.type}</div>
          <div className="text-gray-400">Status: {selectedPoint.status}</div>
          <div className="text-gray-400">Lat: {selectedPoint.lat.toFixed(4)}</div>
          <div className="text-gray-400">Lng: {selectedPoint.lng.toFixed(4)}</div>
        </div>
      )}
    </div>
  )
}