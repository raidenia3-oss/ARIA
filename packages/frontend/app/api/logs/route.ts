import { NextRequest, NextResponse } from "next/server";
import logger from "../../../lib/logger";
import { requireAuth } from "../../../lib/requireAuth";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const auth = requireAuth(request);
  if (auth) return auth;

  const url = new URL(request.url);
  const limit = Number(url.searchParams.get("limit") || 100);
  logger.api("GET", "/api/logs", 0, 200);

  return NextResponse.json({ logs: logger.getLogs(limit) });
}
