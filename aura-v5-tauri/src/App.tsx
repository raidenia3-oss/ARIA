import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Header } from './components/Header/Header'
import { OrbVisual } from './components/OrbVisual/OrbVisual'
import { BackgroundShader } from './components/OrbVisual/BackgroundShader'
import { ChatPanel } from './components/Chat/ChatPanel'
import { ChatInput } from './components/Chat/ChatInput'
import { SkillsSidebar } from './components/Skills/SkillsSidebar'
import { ControlCenter } from './components/Controls/ControlCenter'
import { orbStates, useOrbState } from './hooks/useOrbState'
import { useChat } from './hooks/useChat'
import { useSettings } from './hooks/useSettings'

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

export default function App() {
  const [showControl, setShowControl] = useState(false)
  const [showSkills, setShowSkills] = useState(true)
  const { orbState, setOrbState } = useOrbState()
  const { settings, updateSettings } = useSettings()
  const chat = useChat(setOrbState, { stream: settings.streaming })
  const status = orbStates[orbState]

  const handleSend = (text: string) => {
    if (settings.soundEnabled) blip()
    if (settings.vibration) navigator.vibrate?.(40)
    void chat.sendMessage(text)
  }

  const handleFocusChange = (focused: boolean) => {
    if (focused) setOrbState('listening')
    else setOrbState((prev) => (prev === 'listening' ? 'idle' : prev))
  }

  return (
    <div className="relative flex h-screen w-full flex-col overflow-hidden chat-gradient select-none">
      <BackgroundShader />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-bg-dark-0 via-bg-dark-1 to-bg-dark-2 opacity-80" />
      <div className="hud-grid pointer-events-none absolute inset-0 opacity-[0.10]" />

      <Header
        orbState={orbState}
        showSkills={showSkills}
        onSkillsToggle={() => setShowSkills((value) => !value)}
        onControlClick={() => setShowControl((value) => !value)}
      />

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
          <div className="relative mb-1 h-[230px] w-[230px] shrink-0 md:h-[268px] md:w-[268px]">
            <div
              className="orb-halo"
              style={{ background: `radial-gradient(circle, ${status.glow} 0%, transparent 68%)` }}
            />
            <OrbVisual phase={orbState} animated={settings.animations} />
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