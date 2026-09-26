import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

// Proxies multi-server admin operations to the AME backend.
// The client must send an Authorization: Bearer <jwt> header (minted by
// POST /api/admin/servers/generate-token or scripts/generate-admin-token.ps1).
// GET  -> list servers
// POST -> { action: 'register'|'switch'|'deploy', server_type, credentials?, code_path? }
// PUT  -> { db_url } (sync DATABASE_URL to all registered targets)
// GET  /audit-logs -> read audit log

function backendBase(): string | null {
  return process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || null;
}

export async function GET(req: NextRequest) {
  const backend = backendBase();
  if (!backend) {
    return NextResponse.json({ ok: false, error: "BACKEND_URL no configurado" }, { status: 501 });
  }
  const auth = req.headers.get("authorization");
  if (!auth) {
    return NextResponse.json({ ok: false, error: "Missing authorization" }, { status: 401 });
  }
  try {
    const res = await fetch(`${backend}/api/admin/servers`, {
      cache: "no-store",
      headers: { Authorization: auth },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ ok: false, error: "Backend AME no alcanzable" }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  const backend = backendBase();
  if (!backend) {
    return NextResponse.json({ ok: false, error: "BACKEND_URL no configurado" }, { status: 501 });
  }
  const auth = req.headers.get("authorization");
  if (!auth) {
    return NextResponse.json({ ok: false, error: "Missing authorization" }, { status: 401 });
  }
  try {
    const body = await req.json();
    const res = await fetch(`${backend}/api/admin/servers`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: auth },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ ok: false, error: "Backend AME no alcanzable" }, { status: 502 });
  }
}

export async function PUT(req: NextRequest) {
  const backend = backendBase();
  if (!backend) {
    return NextResponse.json({ ok: false, error: "BACKEND_URL no configurado" }, { status: 501 });
  }
  const auth = req.headers.get("authorization");
  if (!auth) {
    return NextResponse.json({ ok: false, error: "Missing authorization" }, { status: 401 });
  }
  try {
    const body = await req.json();
    const res = await fetch(`${backend}/api/admin/servers`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: auth },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ ok: false, error: "Backend AME no alcanzable" }, { status: 502 });
  }
}
