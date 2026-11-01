/**
 * Segmentador de frases habladas.
 *
 * Escucha el nivel del micrófono y decide cuándo empieza y cuándo termina
 * una frase. Es la pieza que convierte un stream continuo de audio en
 * "órdenes" que se pueden transcribir por separado.
 *
 * La lógica vive aquí, sin navegador, para poder comprobarla con tests:
 * el hook de voz sólo la alimenta con el nivel que lee del analizador.
 */

/** Ajustes del segmentador. */
export interface VoiceGateConfig {
  /** Nivel (0..1) a partir del cual se considera que hay voz. */
  speechThreshold: number
  /** Nivel (0..1) por debajo del cual se considera silencio. */
  silenceThreshold: number
  /** Milisegundos de silencio seguidos que cortan la frase. */
  silenceMs: number
  /** Milisegundos mínimos de voz para que la frase valga. */
  minSpeechMs: number
  /** Milisegundos máximos de una frase antes de cortarla. */
  maxUtteranceMs: number
}

export const DEFAULT_VOICE_GATE: VoiceGateConfig = {
  speechThreshold: 0.06,
  silenceThreshold: 0.02,
  silenceMs: 700,
  minSpeechMs: 350,
  maxUtteranceMs: 15000,
}

/** Eventos que emite el segmentador. */
export type VoiceGateEvent =
  | { type: 'speech-start' }
  | { type: 'speech-end'; reason: 'silence' | 'too-short' | 'max-duration' }

export class VoiceGate {
  private config: VoiceGateConfig
  private speaking = false
  /** Momento en que empezó la frase actual. */
  private startedAt = 0
  /** Última vez que se oyó voz dentro de la frase actual. */
  private lastVoiceAt = 0
  /** Milisegundos con voz real dentro de la frase actual. */
  private speechMs = 0
  /** Momento de la muestra anterior, para medir la voz acumulada. */
  private lastSampleAt = 0
  /** `true` cuando ya hay una muestra previa con la que comparar. */
  private hasSample = false

  constructor(config: Partial<VoiceGateConfig> = {}) {
    this.config = { ...DEFAULT_VOICE_GATE, ...config }
  }

  /** `true` mientras el segmentador está dentro de una frase. */
  get isSpeaking(): boolean {
    return this.speaking
  }

  /** Reinicia el estado: la siguiente voz empieza una frase nueva. */
  reset(): void {
    this.speaking = false
    this.speechMs = 0
  }

  /**
   * Alimenta el segmentador con el nivel actual.
   *
   * @param level Nivel de audio normalizado (0..1).
   * @param now   Marca de tiempo en milisegundos.
   * @returns El evento ocurrido, o `null` si nada cambió.
   */
  update(level: number, now: number): VoiceGateEvent | null {
    // El tiempo con voz se acumula entre muestras: un chasquido de 100 ms
    // seguido de silencio no puede contar como frase.
    if (this.speaking && this.hasSample && level >= this.config.silenceThreshold) {
      this.speechMs += Math.max(0, now - this.lastSampleAt)
    }
    this.lastSampleAt = now
    this.hasSample = true

    if (!this.speaking) {
      if (level >= this.config.speechThreshold) {
        this.speaking = true
        this.startedAt = now
        this.lastVoiceAt = now
        this.speechMs = 0
        return { type: 'speech-start' }
      }
      return null
    }

    // Una frase que se alarga demasiado se corta aunque siga sonando: el
    // micrófono abierto no puede acumular audio infinito.
    if (now - this.startedAt >= this.config.maxUtteranceMs) {
      this.speaking = false
      return { type: 'speech-end', reason: 'max-duration' }
    }

    // Dentro de la frase: la voz reciente mantiene la frase abierta.
    if (level >= this.config.silenceThreshold) {
      this.lastVoiceAt = now
      return null
    }

    if (now - this.lastVoiceAt >= this.config.silenceMs) {
      const reason = this.speechMs < this.config.minSpeechMs ? 'too-short' : 'silence'
      this.speaking = false
      return { type: 'speech-end', reason }
    }

    return null
  }
}

/**
 * Escoge la voz de síntesis que mejor encaja con el idioma.
 *
 * El navegador no garantiza que exista una voz en español: si no hay, se
 * usa la primera disponible y el texto se oye igual, sólo que con otra
 * fonética.
 */
export function pickVoice(
  voices: Array<{ lang: string; name: string }>,
  language: string,
): { lang: string; name: string } | null {
  if (!voices.length) return null
  const prefix = language.split('-')[0].toLowerCase()
  return (
    voices.find((v) => v.lang.toLowerCase() === language.toLowerCase()) ??
    voices.find((v) => v.lang.toLowerCase().startsWith(prefix)) ??
    voices[0]
  )
}
