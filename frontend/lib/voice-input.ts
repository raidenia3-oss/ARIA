"use client";

/**
 * AME Voice Input Hook (Bloque 37, funcionalidad 3).
 *
 * Permite al cliente móvil AME grabar notas de voz locales (MediaRecorder),
 * enviarlas al motor STT local del host AURA (/api/audio/transcribe) y
 * convertirlas a texto antes de sincronizarlas. El audio nunca sale de la red
 * local: se procesa con Faster-Whisper en la PC del escritor.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_AURA_BACKEND_URL || "http://localhost:8000";

export type VoiceInputState =
  | "idle"
  | "recording"
  | "transcribing"
  | "ready"
  | "error";

export interface VoiceInputResult {
  text: string;
  language?: string;
  duration?: number;
  model?: string;
}

export interface UseVoiceInputReturn {
  state: VoiceInputState;
  error: string | null;
  result: VoiceInputResult | null;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<VoiceInputResult | null>;
  transcribeBlob: (blob: Blob, filename?: string) => Promise<VoiceInputResult | null>;
  reset: () => void;
}

function buildHeaders(): Record<string, string> {
  const apiKey = process.env.NEXT_PUBLIC_AURA_API_KEY;
  return apiKey ? { "X-API-Key": apiKey } : {};
}

/** Envía un blob de audio al STT local del host AURA. */
export async function transcribeAudioBlob(
  blob: Blob,
  filename = "voice.webm",
): Promise<VoiceInputResult> {
  const form = new FormData();
  form.append("file", blob, filename);
  const res = await fetch(`${BACKEND_URL}/api/audio/transcribe`, {
    method: "POST",
    body: form,
    headers: buildHeaders(),
    signal: AbortSignal.timeout(120_000),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`STT local falló (${res.status}): ${detail.slice(0, 120)}`);
  }
  const data = (await res.json()) as VoiceInputResult & { status: string };
  return { text: data.text, language: data.language, duration: data.duration, model: data.model };
}

/**
 * Hook de entrada por voz: graba con MediaRecorder y transcribe en el host.
 * Requiere permisos de micrófono del navegador/WebView del móvil.
 */
export function useVoiceInput(): UseVoiceInputReturn {
  const [state, setState] = useState<VoiceInputState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VoiceInputResult | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    setResult(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (ev: BlobEvent) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      recorder.start();
      recorderRef.current = recorder;
      setState("recording");
    } catch (e) {
      setError(e instanceof Error ? e.message : "micrófono no disponible");
      setState("error");
    }
  }, []);

  const stopRecording = useCallback(async (): Promise<VoiceInputResult | null> => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") {
      setState("idle");
      return null;
    }
    setState("transcribing");
    const blob = await new Promise<Blob>((resolve) => {
      recorder.onstop = () => resolve(new Blob(chunksRef.current, { type: recorder.mimeType }));
      recorder.stop();
    });
    streamRef.current?.getTracks().forEach((t) => t.stop());
    recorderRef.current = null;
    try {
      const ext = blob.type.includes("ogg") ? "ogg" : "webm";
      const out = await transcribeAudioBlob(blob, `voice.${ext}`);
      setResult(out);
      setState("ready");
      return out;
    } catch (e) {
      setError(e instanceof Error ? e.message : "transcripción fallida");
      setState("error");
      return null;
    }
  }, []);

  const transcribeBlob = useCallback(
    async (blob: Blob, filename = "voice.webm"): Promise<VoiceInputResult | null> => {
      setState("transcribing");
      try {
        const out = await transcribeAudioBlob(blob, filename);
        setResult(out);
        setState("ready");
        return out;
      } catch (e) {
        setError(e instanceof Error ? e.message : "transcripción fallida");
        setState("error");
        return null;
      }
    },
    [],
  );

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
    setState("idle");
  }, []);

  return { state, error, result, startRecording, stopRecording, transcribeBlob, reset };
}

export default useVoiceInput;