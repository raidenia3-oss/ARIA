import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatController, ChatMessage } from '../../hooks/useChat'

interface ChatPanelProps {
  chat: ChatController
}

function Metadata({ message }: { message: ChatMessage }) {
  if (message.sender === 'user') return null
  const parts: string[] = []
  if (message.source) parts.push(`src:${message.source}`)
  if (typeof message.confidence === 'number') parts.push(`conf:${Math.round(message.confidence)}%`)
  if (message.latency) parts.push(`${message.latency.toFixed(2)}s`)
  if (parts.length === 0) return null
  return (
    <div className="chat-meta glow-dynamic">
      {parts.map((part, i) => (
        <span key={i} className="meta-item">
          <strong>{part}</strong>
        </span>
      ))}
    </div>
  )
}

export function ChatPanel({ chat }: ChatPanelProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat.messages.length, chat.currentStreaming])

  const isEmpty = chat.messages.length === 0 && !chat.isStreaming

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-3">
        {isEmpty && (
          <div className="flex h-full flex-col items-center justify-center text-center gap-2 opacity-70">
            <div className="text-2xl text-accent-cyan">◆</div>
            <p className="text-sm text-text-secondary">ARIA v5.0 lista</p>
            <p className="text-xs text-text-tertiary max-w-sm">
              Pregunta lo que quieras: el orbe reacciona en tiempo real mientras pienso y respondo.
            </p>
          </div>
        )}

        {chat.messages.map((message) => (
          <motion.div
            key={message.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
            className={message.sender === 'user' ? 'flex justify-end' : 'flex justify-start'}
          >
            <div className={message.sender === 'user' ? 'msg-user' : 'msg-aria'}>
              <div className="message-enter markdown-body text-[13px] leading-relaxed">
                {message.sender === 'aria' ? (
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      a: ({ href, children }) => (
                        <a href={href} target="_blank" rel="noreferrer">
                          {children}
                        </a>
                      ),
                    }}
                  >
                    {message.text}
                  </ReactMarkdown>
                ) : (
                  <span className="whitespace-pre-wrap">{message.text}</span>
                )}
              </div>
              <Metadata message={message} />
              <div className="chat-time">{message.timestamp}</div>
            </div>
          </motion.div>
        ))}

        {chat.isStreaming && (
          <div className="flex justify-start">
            <div className="msg-aria">
              <div className="markdown-body text-[13px] leading-relaxed whitespace-pre-wrap">
                {chat.currentStreaming}
                <span className="streaming-cursor" />
              </div>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>
    </div>
  )
}
