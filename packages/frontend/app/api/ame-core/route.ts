import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_AURA_BACKEND_URL || "http://localhost:8000";

async function callBackend(prompt: string, router: boolean = true, feedback?: string, imageUrl?: string, audioUrl?: string, fileUrl?: string, sessionId?: string) {
  const payload: Record<string, unknown> = { prompt, router };
  if (feedback) payload.feedback = feedback;
  if (imageUrl) payload.image_url = imageUrl;
  if (audioUrl) payload.audio_url = audioUrl;
  if (fileUrl) payload.file_url = fileUrl;
  if (sessionId) payload.session_id = sessionId;

  const res = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(process.env.AURA_API_KEY ? { "X-API-Key": process.env.AURA_API_KEY } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Backend error ${res.status}: ${err}`);
  }
  return res.json();
}

export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get("content-type") || "";
    let prompt = "";
    let feedback = "";
    let imageUrl = "";
    let audioUrl = "";
    let fileUrl = "";
    let sessionId = "";

    if (contentType.includes("multipart/form-data")) {
      const formData = await req.formData();
      prompt = (formData.get("prompt") as string) || "";
      feedback = (formData.get("feedback") as string) || "";
      sessionId = (formData.get("session_id") as string) || "";
      const imageFile = formData.get("image") as File | null;
      const audioFile = formData.get("audio") as File | null;
      const docFile = formData.get("file") as File | null;

      if (imageFile && imageFile.size > 0) {
        const bytes = await imageFile.arrayBuffer();
        const base64 = Buffer.from(bytes).toString("base64");
        imageUrl = `data:${imageFile.type || "image/jpeg"};base64,${base64}`;
      }
      if (audioFile && audioFile.size > 0) {
        const bytes = await audioFile.arrayBuffer();
        const base64 = Buffer.from(bytes).toString("base64");
        audioUrl = `data:${audioFile.type || "audio/wav"};base64,${base64}`;
      }
      if (docFile && docFile.size > 0) {
        const bytes = await docFile.arrayBuffer();
        const base64 = Buffer.from(bytes).toString("base64");
        fileUrl = `data:${docFile.type || "application/pdf"};base64,${base64}`;
      }
    } else {
      const body = (await req.json()) as Record<string, string>;
      prompt = (body?.prompt as string) || "";
      feedback = (body?.feedback as string) || "";
      imageUrl = (body?.image_url as string) || "";
      audioUrl = (body?.audio_url as string) || "";
      fileUrl = (body?.file_url as string) || "";
      sessionId = (body?.session_id as string) || "";
    }

    if (!prompt || typeof prompt !== "string") {
      return NextResponse.json({ error: "Prompt requerido" }, { status: 400 });
    }

    const data = await callBackend(prompt, true, feedback || undefined, imageUrl || undefined, audioUrl || undefined, fileUrl || undefined, sessionId || undefined);

    return NextResponse.json({
      result: data.reply || data.text || "",
      provider: data.provider || "unknown",
    });
  } catch (error: unknown) {
    console.error("Error in AME Core API:", error);
    return NextResponse.json(
      { error: "Failed to process request", detail: String(error) },
      { status: 500 }
    );
  }
}

export async function GET(req: NextRequest) {
  try {
    const url = new URL(req.url);
    const prompt = url.searchParams.get("prompt") || "";
    const router = url.searchParams.get("router") === "true";

    if (!prompt) {
      return NextResponse.json({ error: "Prompt requerido" }, { status: 400 });
    }

    const backendUrl = `${BACKEND_URL}/api/chat/stream?prompt=${encodeURIComponent(prompt)}&router=${router}`;
    const backendRes = await fetch(backendUrl, {
      headers: process.env.AURA_API_KEY ? { "X-API-Key": process.env.AURA_API_KEY } : {},
    });

    if (!backendRes.ok) {
      return NextResponse.json({ error: "Backend error", status: backendRes.status }, { status: 502 });
    }

    return new Response(backendRes.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
      },
    });
  } catch (error: unknown) {
    return NextResponse.json({ error: "Stream failed", detail: String(error) }, { status: 500 });
  }
}
