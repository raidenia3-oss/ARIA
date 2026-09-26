import { NextRequest, NextResponse } from "next/server";

// Backend local en desarrollo (server-side only).
const BACKEND_URL = process.env.NEXT_PUBLIC_AURA_BACKEND_URL || "http://localhost:8000";
// Fallback a HF Space si el backend local no esta disponible.
const HF_SPACE_URL = process.env.NEXT_PUBLIC_HF_SPACE_URL;
const HF_TOKEN = process.env.HF_TOKEN;

async function callLocalBackend(message: string, history: unknown[], systemPrompt?: string) {
  const payload: Record<string, unknown> = { prompt: message, router: true };
  if (systemPrompt) payload.context = systemPrompt;

  const res = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    next: { revalidate: 0 },
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Backend error ${res.status}: ${err}`);
  }
  const data = await res.json();
  const botMessage = data.reply || data.text || "";
  const updatedHistory = [...history, [message, botMessage]];
  return { message: botMessage, history: updatedHistory, provider: data.provider || "local" };
}

async function callHFSpace(message: string, history: unknown[], systemPrompt?: string, temperature?: number, maxTokens?: number) {
  if (!HF_SPACE_URL) {
    throw new Error("NEXT_PUBLIC_HF_SPACE_URL no configurado");
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (HF_TOKEN) {
    headers["Authorization"] = `Bearer ${HF_TOKEN}`;
  }

  const response = await fetch(`${HF_SPACE_URL}/run/predict?fn_index=0`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      data: [message, history, systemPrompt, temperature, maxTokens],
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error(`Error from HF Space: ${response.status} ${response.statusText} - ${errorText}`);
    throw new Error(`HF Space error ${response.status}: ${response.statusText}`);
  }

  const result = await response.json();
  const raw = result.data?.[0];
  const botMessage = Array.isArray(raw) ? raw[0] : raw;
  if (!botMessage || typeof botMessage !== "string") {
    console.error("Respuesta inesperada del HF Space:", result);
    throw new Error("Respuesta vacía del Hugging Face Space");
  }

  const updatedHistory = [...history, [message, botMessage]];
  return { message: botMessage, history: updatedHistory, provider: "hf-space" };
}

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as Record<string, unknown>;
    const message: string = (body?.message as string) || "";
    const history: unknown[] = (body?.history as unknown[]) || [];
    const systemPrompt: string | undefined = (body?.systemPrompt as string) || undefined;
    const temperature: number | undefined = (body?.temperature as number) || undefined;
    const maxTokens: number | undefined = (body?.maxTokens as number) || undefined;

    if (!message || typeof message !== "string") {
      return NextResponse.json({ error: "Mensaje requerido" }, { status: 400 });
    }

    // 1) Intentar backend local primero.
    try {
      const localResult = await callLocalBackend(message, history, systemPrompt);
      return NextResponse.json(localResult);
    } catch (localError) {
      console.warn("Backend local no disponible, usando fallback HF:", localError);
    }

    // 2) Fallback a HF Space.
    if (!HF_SPACE_URL) {
      return NextResponse.json(
        { error: "Backend local no disponible y NEXT_PUBLIC_HF_SPACE_URL no configurado." },
        { status: 503 }
      );
    }

    const hfResult = await callHFSpace(message, history, systemPrompt, temperature, maxTokens);
    return NextResponse.json(hfResult);

  } catch (error: unknown) {
    console.error("Error en la ruta /api/hf-chat:", error);
    return NextResponse.json(
      {
        error: "Error interno del servidor",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
