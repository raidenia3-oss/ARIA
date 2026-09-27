# ARIA v6.0 — KILO Phase N: Neural Brain Dashboard

## Propósito
Visualizar agentes en tiempo real como un "cerebro neural" 3D. Cada agente es un nodo que se conecta al centro (ARIA). Cuando un agente está trabajando, el nodo parpadea y se expande.

## Estado Actual
- ✅ Frontend v5 con React 19 + Three.js
- ✅ OrbVisual 3D (7 capas, 12 partículas)
- ✅ Backend FastAPI en puerto 8000 con `/api/agents/status`
- ✅ Swarm con 4 agentes (CodeAnalyzer, DocsWriter, ResearchAgent, Tester)

## Componente Creado
`v5/src/components/NeuralBrain/NeuralBrain.tsx` — SVG-based neural visualization

## Especificaciones
- **Tipo**: SVG (no Three.js para mejor performance)
- **Actualización**: Cada 3 segundos viaje `fetch('/api/agents/status')`
- **Colores por agente**:
  - CodeAnalyzer: #38bdf8 (cyan)
  - DocsWriter: #a78bfa (purple)
  - Tester: #34d399 (green)
  - ResearchAgent: #f59e0b (orange)
- **Estados visuales**:
  - idle: círculo pequeño, opacidad 0.6
  - working: círculo con animación de pulso (r=4→8→4, 1.5s)
  - error: círculo rojo con X

## Integración en App.tsx
```tsx
<div className="glass-panel hidden w-[420px] flex-col items-center rounded-2xl p-3 lg:flex">
  <span className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-accent-purple">
    ◈ Neural Brain
  </span>
  <NeuralBrain />
</div>
```

## Checkpoints
- [x] Componente creado (SVG-based)
- [x] Hook useAgentStatus con polling cada 3s
- [x] Conexiones agentes→centro (líneas punteadas)
- [x] Estados visuales (idle/working/error)
- [x] Stats overlay (active, tasks, errors)
- [x] Integrado en App.tsx
- [x] TypeScript limpio (0 errors)
- [x] Frontend corriendo en :5173

## Próximos Pasos (Phase O)
- Agregar God's Eye View con mapa 3D
- Conectar agentes a ubicaciones geográficas