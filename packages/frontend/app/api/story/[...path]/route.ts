/**
 * Proxy /api/story/[...path] → backend FastAPI (/api/story/...).
 * Mantiene la URL del backend y cualquier credencial del lado del servidor.
 * No almacena ni reenvía tokens: delega la autenticación a la sesión del servidor.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = (
  process.env.NEXT_PUBLIC_AURA_BACKEND_URL ||
  process.env.AURA_BACKEND_URL ||
  "http://localhost:8000"
).replace(/\/$/, "");

type RouteContext = { params: Promise<{ path?: string[] }> };

async function proxy(req: NextRequest, ctx: RouteContext): Promise<NextResponse> {
  const { path } = await ctx.params;
  const sub = (path || []).map(encodeURIComponent).join("/");
  const url = new URL(req.url);
  const qs = url.search || "";
  const target = `${BACKEND_URL}/api/story/${sub}${qs}`;

  try {
    const init: RequestInit = { method: req.method };
    if (req.method !== "GET" && req.method !== "DELETE") {
      init.body = await req.text();
      init.headers = { "Content-Type": "application/json" };
    }
    const res = await fetch(target, init);
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error: unknown) {
    return NextResponse.json(
      { detail: `Backend no disponible: ${error instanceof Error ? error.message : "error"}` },
      { status: 502 }
    );
  }
}

export async function GET(req: NextRequest, ctx: RouteContext) {
  return proxy(req, ctx);
}

export async function POST(req: NextRequest, ctx: RouteContext) {
  return proxy(req, ctx);
}

export async function PUT(req: NextRequest, ctx: RouteContext) {
  return proxy(req, ctx);
}

export async function DELETE(req: NextRequest, ctx: RouteContext) {
  return proxy(req, ctx);
}
