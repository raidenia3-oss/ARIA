import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Header } from './components/Header/Header'
import { OrbVisual } from './components/OrbVisual/OrbVisual'
import { BackgroundShader } from './components/OrbVisual/BackgroundShader'
import { ChatPanel } from './components/Chat/ChatPanel'
import { ChatInput } from './components/Chat/ChatInput'
import { SkillsSidebar } from './components/Skills/SkillsSidebar'
import { ControlCenter } from './components/Controls/ControlCenter'
import { NeuralBrain } from './components/NeuralBrain/NeuralBrain'
import { SkillProgression } from './components/SkillProgression/SkillProgression'
import { GodsEyeView } from './components/GodsEyeView/GodsEyeView'
import { JarvisVoice } from './components/JarvisVoice/JarvisVoice'
import { TabBar } from './components/TabBar/TabBar'
import { orbStates, useOrbState } from './hooks/useOrbState'
import { useChat } from './hooks/useChat'
import { useSettings } from './hooks/useSettings'
import { useBackendTest } from './hooks/useBackendTest'
import { useAriaBackend } from './hooks/useAriaBackend'

/** Blip corto de confirmación (WebAudio, sin assets) */
function blip() {
  try {
    const Ctor =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctor) return
    const ctx = new Ctor()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.value = 880
    gain.gain.setValueAtTime(0.06, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.18)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.2)
    osc.onended = () => void ctx.close()
  } catch {
    /* audio no disponible */
  }
}

export type ActiveView = 'chat' | 'brain' | 'eye' | 'skills' | 'voice'

export default function App() {
  const [showControl, setShowControl] = useState(false)
  const [showSkills, setShowSkills] = useState(true)
  const [showDebug, setShowDebug] = useState(false)
  const [activeView, setActiveView] = useState<ActiveView>('chat')
  const { orbState, setOrbState } = useOrbState()
  const { settings, updateSettings } = useSettings()
  const chat = useChat(setOrbState, { stream: settings.streaming })
  const backendTest = useBackendTest()
  const aria = useAriaBackend()

  // La conexión con Axum (8002) sólo dirige el orbe cuando no hay una
  // fase local activa (chat, escritura, voz). Si el usuario está interactuando,
  // la fase local tiene prioridad.
  const effectivePhase = orbState === 'idle' ? aria.connectionPhase : orbState
  const status = orbStates[effectivePhase]

  useEffect(() => {
    window.electronAPI
      ?.systemStatus()
      .then((payload) => console.log('[ARIA] system status', payload))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    console.log(`[ARIA-Axum] ${aria.connection}`, aria.health ?? aria.lastError)
  }, [aria.connection, aria.health, aria.lastError])

  const handleSend = (text: string) => {
    if (settings.soundEnabled) blip()
    if (settings.vibration) navigator.vibrate?.(40)
    void chat.sendMessage(text)
  }

  const handleFocusChange = (focused: boolean) => {
    if (focused) setOrbState('listening')
    else setOrbState((prev) => (prev === 'listening' ? 'idle' : prev))
  }

  const handleRunTests = () => {
    console.log('🔬 [ARIA] Starting backend test hooks...')
    void backendTest.testAll()
  }

  useEffect(() => {
    if (backendTest.results.length > 0) {
      for (const result of backendTest.results) {
        if (result.success) {
          console.log(`✅ ${result.name} response:`, JSON.stringify(result.data).substring(0, 200))
        } else {
          console.log(`❌ ${result.name} error:`, result.error)
        }
      }
    }
  }, [backendTest.results])

  return (
    <div className="relative flex h-screen w-full flex-col overflow-hidden chat-gradient select-none">
      <BackgroundShader />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-bg-dark-0 via-bg-dark-1 to-bg-dark-2 opacity-80" />
      <div className="hud-grid pointer-events-none absolute inset-0 opacity-[0.10]" />

      <Header
        orbState={effectivePhase}
        showSkills={showSkills}
        onSkillsToggle={() => setShowSkills((value) => !value)}
        onControlClick={() => setShowControl((value) => !value)}
      />

      <TabBar activeView={activeView} onTabChange={setActiveView} />

      {showDebug && (
        <div className="absolute bottom-4 right-4 z-50 flex flex-col gap-2">
          <div className="glass-panel rounded-lg p-3 text-xs">
            <div className="mb-2 flex gap-2">
              <button
                onClick={handleRunTests}
                disabled={backendTest.testing}
                className="rounded-lg bg-cyan-500/20 px-3 py-1 font-medium text-cyan-400 hover:bg-cyan-500/30 disabled:opacity-50"
              >
                {backendTest.testing ? 'Testing...' : 'Test Backend'}
              </button>
              <button
                onClick={backendTest.clear}
                className="rounded-lg bg-gray-500/20 px-2 py-1 text-gray-400"
              >
                Clear
              </button>
              <button
                onClick={() => setShowDebug(false)}
                className="rounded-lg bg-gray-500/20 px-2 py-1 text-gray-400"
              >
                ✕
              </button>
            </div>
            {backendTest.results.length > 0 && (
              <div className="max-h-60 w-64 space-y-1 overflow-y-auto">
                {backendTest.results.map((r, i) => (
                  <div key={i} className={`rounded px-2 py-1 ${r.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                    {r.success ? '✅' : '❌'} {r.name} ({r.latency}ms)
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {!showDebug && (
        <button
          onClick={() => setShowDebug(true)}
          className="fixed bottom-4 right-4 z-50 rounded-full bg-gray-800/50 px-2 py-1 text-xs text-gray-500 opacity-30 hover:opacity-100"
        >
          🐛
        </button>
      )}

      <div className="relative z-10 flex min-h-0 flex-1 overflow-hidden">
        <AnimatePresence initial={false}>
          {showSkills && (
            <motion.aside
              key="skills"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 168, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.28, ease: 'easeInOut' }}
              className="glass-panel m-2 mr-0 overflow-hidden rounded-2xl"
            >
              <SkillsSidebar />
            </motion.aside>
          )}
        </AnimatePresence>

        <main className="flex min-h-0 flex-1 flex-col items-center px-4 py-3">
          <div className="relative mb-1 flex w-full max-w-5xl items-start justify-center gap-4">
            <div className="flex flex-col items-center">
              <div
                className="orb-halo"
                style={{ background: `radial-gradient(circle, ${status.glow} 0%, transparent 68%)` }}
              />
              <OrbVisual phase={effectivePhase} animated={settings.animations} />
            </div>

            <div className={`glass-panel flex w-[420px] flex-col items-center rounded-2xl p-3 ${activeView === 'brain' ? 'flex' : 'hidden'}`}>
              <span className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-accent-purple">
                ◈ Neural Brain
              </span>
              <NeuralBrain />
            </div>

            <div className={`glass-panel flex flex-col items-center rounded-2xl p-3 ${activeView === 'skills' ? 'flex' : 'hidden'}`}>
              <span className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-accent-green">
                ◇ Skill Progression
              </span>
              <SkillProgression />
            </div>

            <div className={`glass-panel flex h-[420px] w-[420px] flex-col items-center rounded-2xl p-3 ${activeView === 'eye' ? 'flex' : 'hidden'}`}>
              <span className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-accent-orange">
                ◎ God's Eye
              </span>
              <GodsEyeView />
            </div>
          </div>

          <div className="glass-panel mb-3 flex min-h-0 w-full max-w-3xl flex-1 flex-col overflow-hidden">
            <ChatPanel chat={chat} />
          </div>

          <div className="w-full max-w-3xl">
            <ChatInput
              onSend={handleSend}
              disabled={chat.isStreaming}
              onFocusChange={handleFocusChange}
            />
          </div>
        </main>
      </div>

      <div className="fixed bottom-4 left-4 z-40">
        <JarvisVoice />
      </div>

      <AnimatePresence>
        {showControl && (
          <motion.div
            key="control"
            initial={{ x: 320, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 320, opacity: 0 }}
            transition={{ duration: 0.28, ease: 'easeInOut' }}
            className="glass-panel absolute right-0 top-11 z-40 h-[calc(100vh-2.75rem)] w-[300px] overflow-hidden rounded-l-2xl"
          >
            <ControlCenter
              settings={settings}
              onUpdate={updateSettings}
              onClose={() => setShowControl(false)}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
