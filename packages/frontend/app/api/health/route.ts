import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET() {
  const body = {
    ok: true,
    timestamp: new Date().toISOString(),
    env: {
      node: process.version,
      vercel: process.env.VERCEL || "false",
      env: process.env.NODE_ENV || "development",
    },
    routes: [
      "/",
      "/ame",
      "/ame/evolution",
      "/ame/[ameId]",
      "/api/webhooks",
      "/api/teams",
      "/api/telegram/webhook",
      "/api/discord/webhook",
      "/api/slack/events",
      "/api/slack/install",
      "/api/health",
      "/api/ame-core",
      "/integrations",
      "/api/integrations/status",
      "/api/logs",
      "/analytics",
    ],
  };
  const res = NextResponse.json(body);
  res.headers.set("cache-control", "no-store");
  return res;
}
