import { auraService } from "./AURAService";

export class VoiceService {
  private recognition: any = null;
  private synthesis: SpeechSynthesis | null = null;
  private isListening = false;
  private onResultCb: ((text: string) => void) | null = null;
  private onErrorCb: ((err: string) => void) | null = null;

  constructor() {
    // SpeechRecognition funciona en WebView de Capacitor
    const SpeechRec =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    if (SpeechRec) {
      this.recognition = new SpeechRec();
      this.recognition.lang = "es-ES";
      this.recognition.continuous = false;
      this.recognition.interimResults = true;

      this.recognition.onresult = (event: any) => {
        const transcript = Array.from(event.results)
          .map((r: any) => r[0].transcript)
          .join("");
        if (event.results[0].isFinal) {
          this.onResultCb?.(transcript);
          this.stopListening();
        }
      };

      this.recognition.onerror = (event: any) => {
        this.onErrorCb?.(event.error);
        this.isListening = false;
      };

      this.recognition.onend = () => {
        this.isListening = false;
      };
    }
    this.synthesis = window.speechSynthesis || null;
  }

  startListening(
    onResult: (text: string) => void,
    onError?: (err: string) => void,
  ): boolean {
    if (!this.recognition) {
      onError?.("Voz no soportada en este dispositivo");
      return false;
    }
    this.onResultCb = onResult;
    this.onErrorCb = onError || null;
    this.recognition.start();
    this.isListening = true;
    return true;
  }

  stopListening(): void {
    this.recognition?.stop();
    this.isListening = false;
  }

  // Hablar texto en español
  speak(text: string, lang = "es-ES"): void {
    if (!this.synthesis) return;
    this.synthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    // Voz en español si esta disponible
    const voices = this.synthesis.getVoices();
    const esVoice = voices.find((v) => v.lang.startsWith("es"));
    if (esVoice) utterance.voice = esVoice;
    this.synthesis.speak(utterance);
  }

  isActive(): boolean {
    return this.isListening;
  }

  // Procesar comando de voz y enviarlo al agente
  async processVoiceCommand(transcript: string): Promise<void> {
    console.log("🎤 Comando de voz:", transcript);
    auraService.send("AGENT_VOICE_CMD", {
      transcript,
      source: "AME_APP",
      ts: Date.now(),
    });
  }
}

export const voiceService = new VoiceService();
