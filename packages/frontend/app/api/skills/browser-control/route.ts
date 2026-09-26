import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

const CLIENT_ACTIONS = ["navigate", "back", "reload", "extractText", "click", "fill"];

export async function GET() {
  const backend = process.env.BACKEND_URL;
  if (!backend) {
    return NextResponse.json({
      ok: true,
      mode: "client-side",
      message:
        "Control en pagina (cliente). Define BACKEND_URL para automatizacion " +
        "headless con Playwright en el backend AME.",
      actions: CLIENT_ACTIONS,
    });
  }
  try {
    const res = await fetch(`${backend}/api/skills/browser-control`, { method: "GET" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ ok: false, error: "Backend AME no alcanzable" }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  const backend = process.env.BACKEND_URL;
  if (!backend) {
    return NextResponse.json(
      { ok: false, error: "BACKEND_URL no configurado. Usa el control en pagina (cliente)." },
      { status: 501 },
    );
  }
  try {
    const body = await req.json();
    const res = await fetch(`${backend}/api/skills/browser-control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ ok: false, error: "Backend AME no alcanzable" }, { status: 502 });
  }
}
