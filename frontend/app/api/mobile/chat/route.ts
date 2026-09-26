import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/mobile/chat
 * Send a message to an AME and get a response.
 * Phase 58 - Option A: Mobile API - Chat
 */

interface ChatRequest {
  ameId: string;
  message: string;
  imageUri?: string;
  audioUri?: string;
}

export async function POST(request: NextRequest) {
  try {
    const rawBody: unknown = await request.json();
    if (!rawBody || typeof rawBody !== "object") {
      return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
    }
    const candidate = rawBody as Partial<ChatRequest>;
    const body: ChatRequest = {
      ameId: typeof candidate.ameId === "string" ? candidate.ameId : "",
      message: typeof candidate.message === "string" ? candidate.message : "",
      imageUri: typeof candidate.imageUri === "string" ? candidate.imageUri : undefined,
      audioUri: typeof candidate.audioUri === "string" ? candidate.audioUri : undefined,
    };
    const { ameId, message, imageUri, audioUri } = body;

    if (!ameId || !message) {
      return NextResponse.json(
        { error: "ameId and message are required" },
        { status: 400 }
      );
    }

    // In production, fetch from backend
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    const apiKey = process.env.AURA_API_KEY || "";

    try {
      const response = await fetch(`${backendUrl}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify({ prompt: message, session_id: ameId, image_base64: imageUri, audio_base64: audioUri, source: "ame" }),
        signal: AbortSignal.timeout(60000),
      });

      if (response.ok) {
        const data = await response.json();
        return NextResponse.json(data);
      }

      if (response.status === 401) {
        return NextResponse.json({ error: "Backend authentication failed" }, { status: 401 });
      }
      if (response.status === 404) {
        return NextResponse.json({ error: "Backend chat endpoint not found" }, { status: 404 });
      }
      return NextResponse.json({ error: `Backend chat failed (${response.status})` }, { status: 502 });
    } catch (error) {
      console.warn("Backend unavailable for mobile chat:", error);
    }

    return NextResponse.json({ error: "AURA backend unavailable" }, { status: 503 });
  } catch (error) {
    console.error("Mobile chat API error:", error);
    return NextResponse.json(
      { error: "Failed to process message" },
      { status: 500 }
    );
  }
}