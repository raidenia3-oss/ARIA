const METRICS = [
  { label: 'CPU_NÚCLEO', value: 34, unit: '%', status: 'success' },
  { label: 'RAM_BUFFER', value: 12.4, unit: 'GB', status: 'primary' },
  { label: 'GPU_TENSOR', value: 78, unit: '%', status: 'warning' },
  { label: 'VRAM_ALLOC', value: 4.2, unit: 'GB', status: 'primary' },
  { label: 'WEBRTC_PKT', value: 2.4, unit: 'ms', status: 'success' },
  { label: 'SWARM_NODES', value: 8, unit: 'activos', status: 'success' },
]

export default function TacticalMatrix({ mode = 'ECO' }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
      {METRICS.map((m) => (
        <div
          key={m.label}
          className="rounded-lg border border-aura-border/40 bg-aura-surface/60 p-3 backdrop-blur-sm"
        >
          <div className="text-[10px] font-bold uppercase tracking-widest text-aura-muted">{m.label}</div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-xl font-bold text-aura-primary">{m.value}</span>
            <span className="text-[10px] text-aura-muted">{m.unit}</span>
          </div>
          <div className="mt-2 h-1 w-full rounded-full bg-aura-bg">
            <div
              className="h-1 rounded-full bg-aura-primary"
              style={{ width: `${Math.min(100, Math.max(0, m.value))}%` }}
            />
          </div>
        </div>
      ))}

      <div className="col-span-2 rounded-lg border border-aura-border/40 bg-aura-surface/60 p-3 md:col-span-1">
        <div className="text-[10px] font-bold uppercase tracking-widest text-aura-muted">Modo Operativo</div>
        <div className="mt-2 flex items-center justify-between">
          <span className="text-sm font-bold text-aura-warning">{mode}</span>
          <span className="text-[10px] text-aura-muted">
            {mode === 'ECO' ? 'AHORRO ENERGÉTICO' : 'RENDIMIENTO MÁXIMO'}
          </span>
        </div>
        <div className="mt-3 flex gap-2">
          <button className="flex-1 rounded border border-aura-border px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-aura-primary hover:bg-aura-primary/10 transition-colors">
            Diagnóstico
          </button>
          <button className="flex-1 rounded border border-aura-border px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-aura-danger hover:bg-aura-danger/10 transition-colors">
            Purga
          </button>
        </div>
      </div>
    </div>
  )
}
