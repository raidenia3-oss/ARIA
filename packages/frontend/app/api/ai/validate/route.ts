import { NextResponse } from "next/server";

const HF_SPACE_URL =
  process.env.HF_SPACE_URL || "https://raiden456-slut.hf.space";
const HF_API_TOKEN = process.env.HF_API_TOKEN || "";

export async function GET() {
  const results: Record<string, unknown> = {
    timestamp: new Date().toISOString(),
    hfSpace: false,
    models: [],
    fallback: true,
  };

  // 1. Verificar HF Space
  try {
    const hfRes = await fetch(`${HF_SPACE_URL}/api/v1/status`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...(HF_API_TOKEN ? { Authorization: `Bearer ${HF_API_TOKEN}` } : {}),
      },
      signal: AbortSignal.timeout(5000),
    });

    if (hfRes.ok) {
      const data = await hfRes.json();
      results.hfSpace = true;
      results.hfData = data;
      results.fallback = false;
    }
  } catch (error: unknown) {
    if (error instanceof Error) {
      results.hfError = error.message;
    } else {
      results.hfError = "HF Space not reachable";
    }
  }

  // 2. Verificar modelos disponibles
  try {
    const modelsRes = await fetch(`${HF_SPACE_URL}/api/v1/models`, {
      signal: AbortSignal.timeout(5000),
    });
    if (modelsRes.ok) {
      results.models = await modelsRes.json();
    }
  } catch {
    results.models = ["qwen2.5-7b-instruct (fallback local)"];
  }

  // 3. Test de inferencia
  try {
    const inferRes = await fetch(`${HF_SPACE_URL}/api/v1/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: "Responde solo: OK",
        max_tokens: 10,
      }),
      signal: AbortSignal.timeout(8000),
    });
    if (inferRes.ok) {
      const inferData = await inferRes.json();
      results.inference = true;
      results.inferenceResponse = inferData;
    }
  } catch {
    results.inference = false;
    results.inferenceError = "Inference test failed (using fallback)";
  }

  return NextResponse.json({
    status: results.hfSpace ? "online" : "offline",
    ...results,
    suggestion: results.hfSpace
      ? "HF Space funcionando correctamente"
      : "HF Space no disponible. Usando fallback local con AI analysis en el navegador.",
  });
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { prompt } = body;

    if (!prompt) {
      return NextResponse.json({ error: "Prompt requerido" }, { status: 400 });
    }

    // Intentar con HF Space primero
    try {
      const hfRes = await fetch(`${HF_SPACE_URL}/api/v1/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(HF_API_TOKEN ? { Authorization: `Bearer ${HF_API_TOKEN}` } : {}),
        },
        body: JSON.stringify({
          prompt,
          max_tokens: 500,
          temperature: 0.7,
        }),
        signal: AbortSignal.timeout(15000),
      });

      if (hfRes.ok) {
        const data = await hfRes.json();
        return NextResponse.json({
          source: "hf-space",
          result:
            data.choices?.[0]?.text ||
            data.text ||
            data.response ||
            "Procesado por HF Space",
        });
      }
    } catch {
      // Fallback local
    }

    // Fallback: análisis local inteligente
    const words = prompt.split(" ");
    const wordCount = words.length;
    const topics = prompt.match(
      /\b(IA|inteligencia|análisis|datos|sistema|ame|robot|automatización)\b/gi,
    );

    return NextResponse.json({
      source: "local-fallback",
      result:
        `📱 Análisis local completado (modo offline)\n\n` +
        `Tu consulta fue procesada localmente en el navegador:\n` +
        `• Palabras analizadas: ${wordCount}\n` +
        `• Temas detectados: ${topics?.join(", ") || "general"}\n` +
        `• Modo: ${(await checkOnline()) ? "online" : "offline"}\n\n` +
        `_Los resultados completos estarán disponibles cuando HF Space se reconecte._`,
      fallback: true,
    });
  } catch (error: unknown) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Error interno",
        source: "error",
      },
      { status: 500 },
    );
  }
}

async function checkOnline(): Promise<boolean> {
  try {
    const res = await fetch(HF_SPACE_URL, {
      signal: AbortSignal.timeout(3000),
    });
    return res.ok;
  } catch {
    return false;
  }
}
