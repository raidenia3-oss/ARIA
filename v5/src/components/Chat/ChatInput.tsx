import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface ChatInputProps {
  onSend: (text: string) => void
  disabled?: boolean
  placeholder?: string
  onFocusChange?: (focused: boolean) => void
}

function PaperclipIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
    </svg>
  )
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
      <path d="M19 10v2a7 7 0 01-14 0v-2M12 19v4M8 23h8" />
    </svg>
  )
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = 'Escribe un mensaje...',
  onFocusChange,
}: ChatInputProps) {
  const [text, setText] = useState('')
  const [showHint, setShowHint] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`
  }, [text])

  const submit = () => {
    if (!text.trim() || disabled) return
    onSend(text.trim())
    setText('')
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  const hasText = text.trim().length > 0

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
      className="w-full"
    >
      <div className="relative">
        <AnimatePresence>
          {showHint && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="flex items-center gap-4 px-3 pb-1.5 text-[11px] text-text-tertiary"
            >
              <span className="flex items-center gap-1.5">
                <PaperclipIcon /> Adjuntos
              </span>
              <span className="flex items-center gap-1.5">
                <MicIcon /> Voz
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex items-end gap-2 p-2.5 glass-panel rounded-2xl">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => onFocusChange?.(true)}
            onBlur={() => onFocusChange?.(false)}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className="flex-1 bg-transparent border-0 outline-none resize-none text-text-primary placeholder-text-tertiary px-2 py-2 max-h-[140px] no-drag"
            style={{ lineHeight: '24px' }}
            aria-label="Mensaje"
          />

          <div className="flex items-center gap-1">
            <motion.button
              type="button"
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.92 }}
              onClick={() => setShowHint((value) => !value)}
              className="btn-glow p-2 rounded-lg text-text-tertiary hover:text-accent-cyan"
              aria-label="Adjuntar archivos"
            >
              <PaperclipIcon />
            </motion.button>

            <motion.button
              type="button"
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.92 }}
              className="btn-glow p-2 rounded-lg text-text-tertiary hover:text-accent-purple"
              aria-label="Comando de voz"
            >
              <MicIcon />
            </motion.button>

            <AnimatePresence>
              {hasText && !disabled && (
                <motion.button
                  type="submit"
                  initial={{ opacity: 0, scale: 0.7 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.7 }}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.92 }}
                  className="btn-glow p-2.5 rounded-xl bg-gradient-to-br from-accent-cyan to-accent-purple text-white"
                  aria-label="Enviar mensaje"
                >
                  <SendIcon />
                </motion.button>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </form>
  )
}
