import { useState } from 'react'
import { Camera, Cpu, Mic, Zap, Brain } from 'lucide-react'

const ACTIONS = [
  { id: 'analyze-vision', label: 'Analizar Entorno', icon: Camera, color: '#38bdf8', action: 'analyze_environment' },
  { id: 'clear-ram', label: 'Limpiar RAM', icon: Cpu, color: '#a855f7', action: 'clear_ram' },
  { id: 'network-diag', label: 'Diagnóstico de Red', icon: Zap, color: '#22c55e', action: 'network_diag' },
  { id: 'voice-command', label: 'Comando de Voz', icon: Mic, color: '#f59e0b', action: 'voice_command' },
  { id: 'memory-recall', label: 'Buscar Memoria', icon: Brain, color: '#6366f1', action: 'memory_recall' },
  { id: 'suspend-swarm', label: 'Suspender Swarm', icon: Cpu, color: '#ef4444', action: 'suspend_swarm' },
]

export default function QuickActions({ theme }) {
  const [loadingId, setLoadingId] = useState(null)
  const [results, setResults] = useState([])

  const execute = async (actionItem) => {
    setLoadingId(actionItem.id)
    try {
      if (actionItem.action === 'analyze_environment') {
        const stream = await navigator.mediaDevices.getDisplayMedia({ video: true })
        const video = document.createElement('video')
        video.srcObject = stream
        await video.play()
        await new Promise(resolve => setTimeout(resolve, 500))
        const canvas = document.createElement('canvas')
        canvas.width = video.videoWidth || 640
        canvas.height = video.videoHeight || 480
        const ctx = canvas.getContext('2d')
        ctx.drawImage(video, 0, 0)
        const img_b64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1]
        stream.getTracks().forEach(track => track.stop())
        const res = await fetch('/api/vision/analyze-frame', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image: img_b64, session_id: 'web-dashboard' }),
        })
        const data = await res.json()
        const text = data?.summary || data?.description || JSON.stringify(data)
        setResults(prev => [...prev, { id: Date.now(), text: `[SYSTEM_VISION_CONTEXT] ${text}` }])
      } else if (actionItem.action === 'memory_recall') {
        const query = prompt('Buscar en memoria:')
        if (!query) return
        const res = await fetch(`/api/memory/search?q=${encodeURIComponent(query)}&limit=5`)
        const data = await res.json()
        const context = (data.context || data.results || []).map((m) => m.text || JSON.stringify(m)).join('\n')
        setResults(prev => [...prev, { id: Date.now(), text: `[MEMORY] ${context || 'Sin resultados'}` }])
      } else {
        const res = await fetch('/api/actions/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tool: actionItem.action, params: {}, approved: true }),
        })
        const data = await res.json()
        setResults(prev => [...prev, { id: Date.now(), text: data.output || data.error || JSON.stringify(data) }])
      }
    } catch (e) {
      setResults(prev => [...prev, { id: Date.now(), text: `Error: ${e.message}` }])
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <div className="quick-actions">
      <div className="quick-actions-header">
        <h3>Quick Actions</h3>
        <span className="quick-actions-badge">READY</span>
      </div>
      <div className="quick-actions-grid">
        {ACTIONS.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.id}
              className="quick-action-btn"
              style={{ '--action-color': item.color }}
              onClick={() => execute(item)}
              disabled={loadingId === item.id}
            >
              {loadingId === item.id && <div className="quick-action-spinner"></div>}
              <Icon className="quick-action-icon" style={{ color: item.color }} />
              <span className="quick-action-label">{item.label}</span>
            </button>
          )
        })}
      </div>
      {results.length > 0 && (
        <div className="quick-actions-results">
          {results.map((r) => (
            <div key={r.id} className="quick-result-item">
              <span className="quick-result-text">{r.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
