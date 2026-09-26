import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/ai/multimodal
 *
 * Proxy fiel al backend AURA. Reenvía la imagen como multipart al endpoint
 * nativo de vision del backend (/api/vision, que usa Gemini 2.0 Flash) y el
 * texto al chat (/api/chat). El backend indexa el analisis en semantic_memory
 * con kind="[VISION]".
 *
 * Formato de entrada esperado (multipart):
 *   - file: imagen (png/jpeg/webp)
 *   - prompt: texto opcional
 */

export async function POST(request: NextRequest) {
  const startTime = Date.now();
  const backendUrl = (
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"
  ).replace(/\/+$/, "");

  const contentType = request.headers.get("content-type") || "";

  try {
    // --- Entrada multipart (imagen + prompt) ---
    if (contentType.includes("multipart/form-data")) {
      const form = await request.formData();
      const file = form.get("file");
      const prompt = (form.get("prompt") as string) || "Describe esta imagen en detalle.";

      if (!(file instanceof File)) {
        return NextResponse.json(
          { error: "Se requiere un archivo de imagen en el campo 'file'." },
          { status: 400 }
        );
      }

      const fd = new FormData();
      fd.append("file", file, file.name || "image");
      fd.append("prompt", prompt);

      const visionResp = await fetch(`${backendUrl}/api/vision`, {
        method: "POST",
        body: fd,
        signal: AbortSignal.timeout(60000),
      });

      const visionData = await visionResp.json().catch(() => ({}));
      if (!visionResp.ok) {
        return NextResponse.json(
          { error: "Vision backend error", details: visionData },
          { status: visionResp.status }
        );
      }

      return NextResponse.json({
        imageAnalysis: {
          description: visionData.analysis || "",
          objects: [],
          sentiment: "neutral",
        },
        rawOutput: {
          processingTimeMs: Date.now() - startTime,
          modalities: { text: !!prompt, image: true },
          provider: visionData.provider,
        },
      });
    }

    // --- Entrada JSON (texto solo, o base64 legacy) ---
    const body = (await request.json().catch(() => ({}))) as {
      text?: string;
      imageBase64?: string;
      prompt?: string;
    };
    const { text, imageBase64, prompt } = body;

    if (imageBase64) {
      const res = await fetch(`${backendUrl}/api/vision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imageBase64, prompt: prompt || text }),
        signal: AbortSignal.timeout(60000),
      });
      const data = await res.json().catch(() => ({}));
      return NextResponse.json({
        imageAnalysis: {
          description: data.analysis || "",
          objects: [],
          sentiment: "neutral",
        },
        rawOutput: { processingTimeMs: Date.now() - startTime, modalities: { image: true } },
      });
    }

    if (text) {
      const res = await fetch(`${backendUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text }),
        signal: AbortSignal.timeout(30000),
      });
      const data = await res.json().catch(() => ({}));
      return NextResponse.json({
        textAnalysis: {
          understanding: `Analyzed: "${text.substring(0, 100)}..."`,
          response: data.reply || data.response || data.message || "",
          confidence: 0.85,
        },
        rawOutput: { processingTimeMs: Date.now() - startTime, modalities: { text: true } },
      });
    }

    return NextResponse.json(
      { error: "At least one input modality required (text or image)" },
      { status: 400 }
    );
  } catch (error) {
    console.error("Multimodal proxy error:", error);
    return NextResponse.json(
      {
        error: "Failed to proxy multimodal request",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}

/**
 * GET /api/ai/model-info
 * Returns information about the current AI model.
 */
export async function GET() {
  return NextResponse.json({
    model: "gemini-2.0-flash",
    capabilities: ["text", "image"],
    status: "operational",
    backend: process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000",
  });
}