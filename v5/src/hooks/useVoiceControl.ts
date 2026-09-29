import { useEffect, useRef, useState } from 'react'

interface SpeechRecognitionResultLike {
  transcript: string
}

interface SpeechRecognitionEventLike {
  resultIndex: number
  results: { length: number; [i: number]: { isFinal: boolean; [0]: SpeechRecognitionResultLike } }
}

interface SpeechRecognitionErrorEventLike {
  error: string
}

type SR = {
  new (): {
    continuous: boolean
    interimResults: boolean
    lang: string
    onstart: (() => void) | null
    onend: (() => void) | null
    onresult: ((event: SpeechRecognitionEventLike) => void) | null
    onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null
    start(): void
    stop(): void
    abort(): void
  }
}

declare global {
  interface Window {
    SpeechRecognition?: SR
    webkitSpeechRecognition?: SR
  }
}

export interface VoiceCommand {
  transcript: string
  agent: string
  action: string
  confidence: number
}

const AXUM_ORIGIN = 'http://127.0.0.1:8002'

export function useVoiceControl() {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const recognitionRef = useRef<InstanceType<SR> | null>(null)

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return

    recognitionRef.current = new SR()
    recognitionRef.current.continuous = true
    recognitionRef.current.interimResults = true
    recognitionRef.current.lang = 'en-US'

    recognitionRef.current.onstart = () => setIsListening(true)
    recognitionRef.current.onend = () => setIsListening(false)

    recognitionRef.current.onresult = (event: SpeechRecognitionEventLike) => {
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        interim += event.results[i][0].transcript
      }
      setTranscript(interim)

      if (event.results[event.results.length - 1].isFinal) {
        setIsProcessing(true)
        void processCommand(interim)
        setIsProcessing(false)
      }
    }

    recognitionRef.current.onerror = (event: SpeechRecognitionErrorEventLike) => {
      console.error('Speech recognition error', event.error)
    }

    return () => { recognitionRef.current?.abort() }
  }, [])

  const startListening = () => {
    setTranscript('')
    recognitionRef.current?.start()
  }

  const stopListening = () => {
    recognitionRef.current?.stop()
  }

  const processCommand = async (text: string) => {
    try {
      const response = await fetch(`${AXUM_ORIGIN}/api/agents/voice/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      const result = await response.json() as { response?: string }
      const utterance = new SpeechSynthesisUtterance(result.response || 'Command processed')
      utterance.rate = 1
      speechSynthesis.speak(utterance)
    } catch (err) {
      console.error('Command processing failed', err)
    }
  }

  return { isListening, transcript, isProcessing, startListening, stopListening }
}