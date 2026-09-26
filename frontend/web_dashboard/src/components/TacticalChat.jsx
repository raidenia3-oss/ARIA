import React, { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Mic, Zap, Brain } from 'lucide-react'
import '../styles/TacticalChat.css'

const AGENTS = [
  { id: 'C-01', name: 'Sanctuary', role: 'Orchestrator', status: 'online' },
  { id: 'C-02', name: 'Pulse', role: 'Monitor', status: 'online' },
  { id: 'C-03', name: 'Resonance', role: 'Communicator', status: 'online' },
  { id: 'C-04', name: 'Sentencia', role: 'Judge', status: 'online' },
]

export default function TacticalChat({ theme, telemetry }) {
  const [selectedAgent, setSelectedAgent] = useState(AGENTS[0])
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isListening, setIsListening] = useState(false)
  const [loading, setLoading] = useState(false)
  const [memoryHint, setMemoryHint] = useState('')
  const messagesEndRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const res = await fetch('/api/chat')
        if (!res.ok) return
        const data = await res.json()
        if (Array.isArray(data)) {
          setMessages(
            data.map((m) => ({
              id: m.id || Date.now() + Math.random(),
              text: m.text || m.message || '',
              sender: m.sender === 'user' ? 'user' : 'agent',
              timestamp: new Date(m.timestamp || Date.now()),
            }))
          )
        }
      } catch (e) {
        console.error('[chat] history load failed', e)
      }
    }
    loadHistory()
  }, [])

  const searchMemory = async (query) => {
    try {
      const res = await fetch(`/api/memory/search?q=${encodeURIComponent(query)}&limit=3`)
      if (res.ok) {
        const data = await res.json()
        const context = (data.context || data.results || []).map((m) => m.text || m).join(' | ')
        if (context) setMemoryHint(context)
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

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const userMessage = {
      id: Date.now(),
      text: input,
      sender: 'user',
      timestamp: new Date(),
    }
    await searchMemory(input.trim())
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)
    try {
      const payload = { message: memoryHint ? `${memoryHint}\n\n${userMessage.text}` : userMessage.text }
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      const reply = data?.reply || data?.message || data?.text || 'El backend no devolvió respuesta legible.'
      const agentMessage = {
        id: Date.now() + 1,
        text: reply,
        sender: 'agent',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, agentMessage])
      rememberResponse(userMessage.text, reply)
    } catch (e) {
      console.error('[chat] send failed', e)
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          text: 'Error de conexión con /api/chat.',
          sender: 'agent',
          timestamp: new Date(),
        },
      ])
    } finally {
      setLoading(false)
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
              body: JSON.stringify({ session_id: 'web-chat', audio: base64Audio }),
            })
            const data = await res.json()
            if (data.status === 'queued') {
              setMessages((prev) => [...prev, { id: Date.now(), sender: 'agent', text: '[AUDIO] Audio enviado al pipeline de STT.', timestamp: new Date() }])
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

  return (
    <div className="tactical-chat">
      <div className="chat-container">
        <div className="agent-selector glass">
          <div className="selector-header">
            <h3>SELECT AGENT</h3>
          </div>
          <div className="agent-list">
            {AGENTS.map((agent) => (
              <motion.button
                key={agent.id}
                className={`agent-btn ${selectedAgent.id === agent.id ? 'active' : ''}`}
                onClick={() => setSelectedAgent(agent)}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                style={{
                  borderColor:
                    selectedAgent.id === agent.id
                      ? theme
                      : 'rgba(224, 232, 255, 0.1)',
                }}
              >
                <div className="agent-info">
                  <span className="agent-name">{agent.name}</span>
                  <span className="agent-role">{agent.role}</span>
                </div>
                <span className={`agent-status ${agent.status}`}>●</span>
              </motion.button>
            ))}
          </div>
        </div>

        <div className="chat-area glass">
          <div className="chat-header" style={{ borderColor: theme }}>
            <h2>{selectedAgent.name}</h2>
            <span className="chat-subtitle">{selectedAgent.role}</span>
          </div>

          <div className="messages">
            <AnimatePresence>
              {messages.length === 0 ? (
                <motion.div
                  className="empty-state"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <Zap size={32} style={{ color: theme }} />
                  <p>Awaiting commands...</p>
                </motion.div>
              ) : (
                messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    className={`message ${msg.sender}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <div className="message-bubble">
                      <p>{msg.text}</p>
                      <span className="message-time">
                        {msg.timestamp.toLocaleTimeString()}
                      </span>
                    </div>
                  </motion.div>
                ))
              )}
            </AnimatePresence>
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            <div className="input-wrapper">
              <input
                type="text"
                placeholder="Enter command..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                style={{ borderColor: theme }}
              />
              <motion.button
                className="mic-btn"
                onClick={isListening ? stopListening : startListening}
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                style={{
                  background: isListening ? theme : 'transparent',
                  color: isListening ? '#fff' : theme,
                }}
              >
                <Mic size={20} />
              </motion.button>
              <motion.button
                className="send-btn"
                onClick={handleSend}
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                style={{ background: theme }}
              >
                <Send size={20} />
              </motion.button>
            </div>
            <div className="input-hint">
              💡 Use natural language or slash commands {memoryHint && '| 🧠 Memory context loaded'}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
