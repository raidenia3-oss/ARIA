import { useState, useRef, useEffect } from 'react'
import { Send, Cpu, Zap, Mic, Square, Camera, Brain } from 'lucide-react'

const MESSAGES = [
  { id: 1, from: 'AURA', text: 'Núcleo sináptico en línea. ¿Cuál es la directiva?', time: '22:48:01' },
  { id: 2, from: 'USER', text: 'Analizar tendencias de latencia en WebRTC.', time: '22:48:04' },
  { id: 3, from: 'AURA', text: 'Iniciando escaneo... Latencia media: 2.4ms. Sin anomalías detectadas.', time: '22:48:06' },
]

const AGENTS = [
  { id: 'AURA', label: 'AURA_CORE' },
  { id: 'SWARM', label: 'SWARM_COORD' },
  { id: 'VISION', label: 'VISION_NET' },
  { id: 'AUDIO', label: 'AUDIO_STREAM' },
]

export default function AuraConsole() {
  const [messages, setMessages] = useState(MESSAGES)
  const [input, setInput] = useState('')
  const [target, setTarget] = useState('AURA')
  const [isListening, setIsListening] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [memoryContext, setMemoryContext] = useState('')
  const endRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const searchMemory = async (query) => {
    try {
      const res = await fetch(`/api/memory/search?q=${encodeURIComponent(query)}&limit=3`)
      if (res.ok) {
        const data = await res.json()
        const context = (data.context || data.results || []).map((m) => m.text || m).join(' | ')
        if (context) setMemoryContext(context)
      }
    } catch (e) {
      console.error('[memory] search failed', e)
    }
  }

  const rememberResponse = async (prompt, response) => {
    try {
      await fetch('/api/memory/remember', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: `User: ${prompt}\nAURA: ${response}`, type: 'episodic', source: 'web_dashboard' }),
      })
    } catch (e) {
      console.error('[memory] remember failed', e)
    }
  }

  const send = async () => {
    if (!input.trim()) return
    const text = input.trim()
    await searchMemory(text)
    setMessages(prev => [...prev, { id: Date.now(), from: 'USER', text, time: new Date().toLocaleTimeString('es-ES', { hour12: false }) }])
    setInput('')
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: memoryContext ? `${memoryContext}\n\n${text}` : text }),
      })
      const data = await res.json()
      const reply = data?.reply || data?.message || data?.text || 'El backend no devolvió respuesta legible.'
      setMessages(prev => [...prev, { id: Date.now() + 1, from: target, text: reply, time: new Date().toLocaleTimeString('es-ES', { hour12: false }) }])
      rememberResponse(text, reply)
    } catch (e) {
      setMessages(prev => [...prev, { id: Date.now() + 1, from: target, text: 'Error de conexión con /api/chat.', time: new Date().toLocaleTimeString('es-ES', { hour12: false }) }])
    }
  }

  const startListening = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data)
      }
      mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        const reader = new FileReader()
        reader.onloadend = async () => {
          const base64Audio = reader.result.split(',')[1]
          try {
            const res = await fetch('/api/webrtc/audio/process', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ session_id: 'web-session', audio: base64Audio }),
            })
            const data = await res.json()
            if (data.status === 'queued') {
              setMessages(prev => [...prev, { id: Date.now(), from: 'AURA', text: '[AUDIO] Audio enviado al pipeline de STT.', time: new Date().toLocaleTimeString('es-ES', { hour12: false }) }])
            }
          } catch (e) {
            console.error('[audio] send failed', e)
          }
        }
        reader.readAsDataURL(blob)
        stream.getTracks().forEach(track => track.stop())
      }
      mediaRecorder.start()
      setIsListening(true)
    } catch (e) {
      console.error('[audio] mic error', e)
    }
  }

  const stopListening = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    setIsListening(false)
  }

  const analyzeViewport = async () => {
    setIsAnalyzing(true)
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true })
      const video = document.createElement('video')
      video.srcObject = stream
      await video.play()
      await new Promise(resolve => setTimeout(resolve, 500))
      const canvas = document.createElement('canvas')
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0)
      const img_b64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1]
      stream.getTracks().forEach(track => track.stop())
      const res = await fetch('/api/vision/analyze-frame', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: img_b64, session_id: 'web-session' }),
      })
      const data = await res.json()
      const visionText = data?.summary || data?.description || JSON.stringify(data)
      setMessages(prev => [...prev, { id: Date.now(), from: 'SYSTEM_VISION_CONTEXT', text: `[SYSTEM_VISION_CONTEXT] ${visionText}`, time: new Date().toLocaleTimeString('es-ES', { hour12: false }) }])
    } catch (e) {
      console.error('[vision] analyze failed', e)
    } finally {
      setIsAnalyzing(false)
    }
  }

  return (
    <div className="flex h-[260px] flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-widest text-aura-primary">Terminal AURA</h3>
        <div className="flex items-center gap-2">
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="rounded border border-aura-border bg-aura-surface px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-aura-primary outline-none"
          >
            {AGENTS.map(a => (
              <option key={a.id} value={a.id}>{a.label}</option>
            ))}
          </select>
          <Cpu className="h-3 w-3 text-aura-success" />
          <Zap className="h-3 w-3 text-aura-warning" />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto rounded-lg border border-aura-border/40 bg-aura-bg/60 p-3">
        {messages.map((msg) => (
          <div key={msg.id} className="mb-2 flex flex-col gap-0.5">
            <div className="flex items-baseline gap-2">
              <span className={`text-[10px] font-bold ${msg.from === 'USER' ? 'text-aura-warning' : msg.from === 'SYSTEM_VISION_CONTEXT' ? 'text-aura-primary' : 'text-aura-primary'}`}>
                {msg.from}
              </span>
              <span className="text-[9px] text-aura-muted">{msg.time}</span>
            </div>
            <p className="text-xs leading-relaxed text-slate-300">{msg.text}</p>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Escribir comando..."
          className="flex-1 rounded border border-aura-border bg-aura-surface px-3 py-2 text-xs text-slate-200 outline-none placeholder:text-aura-muted focus:border-aura-primary"
        />
        <button
          onClick={isListening ? stopListening : startListening}
          className={`rounded border px-3 py-2 transition-colors ${isListening ? 'border-aura-error bg-aura-error/20 text-aura-error' : 'border-aura-primary bg-aura-primary/10 text-aura-primary hover:bg-aura-primary/20'}`}
        >
          {isListening ? <Square className="h-3 w-3" /> : <Mic className="h-3 w-3" />}
        </button>
        <button
          onClick={analyzeViewport}
          disabled={isAnalyzing}
          className="rounded border border-aura-primary bg-aura-primary/10 px-3 py-2 text-aura-primary hover:bg-aura-primary/20 transition-colors disabled:opacity-50"
        >
          <Camera className="h-3 w-3" />
        </button>
        <button
          onClick={send}
          className="rounded border border-aura-primary bg-aura-primary/10 px-3 py-2 text-aura-primary hover:bg-aura-primary/20 transition-colors"
        >
          <Send className="h-3 w-3" />
        </button>
      </div>
      {memoryContext && (
        <div className="text-[10px] text-aura-muted truncate">
          🧠 Memoria activa: {memoryContext.substring(0, 80)}...
        </div>
      )}
    </div>
  )
}
