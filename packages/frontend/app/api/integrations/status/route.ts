import { NextResponse } from "next/server";
import { WebhookManager } from "../../../../lib/webhook-manager";

export const runtime = "nodejs";

export async function GET() {
  const webhooks = WebhookManager.getAll();

  const status = {
    slack: {
      connected: Boolean(process.env.SLACK_CLIENT_ID),
      note: process.env.SLACK_CLIENT_ID
        ? "App configurada"
        : "Falta SLACK_CLIENT_ID",
    },
    discord: {
      connected: Boolean(process.env.DISCORD_TOKEN),
      note: process.env.DISCORD_TOKEN
        ? "Bot configurado"
        : "Falta DISCORD_TOKEN",
    },
    telegram: {
      connected: Boolean(process.env.TELEGRAM_TOKEN),
      note: process.env.TELEGRAM_TOKEN
        ? "Bot configurado"
        : "Falta TELEGRAM_TOKEN",
    },
    teams: {
      connected: Boolean(process.env.TEAMS_APP_ID),
      note: process.env.TEAMS_APP_ID
        ? "App configurada"
        : "Falta TEAMS_APP_ID",
    },
    webhooks: {
      connected: webhooks.length > 0,
      count: webhooks.length,
      note:
        webhooks.length > 0
          ? `${webhooks.length} webhook(s) activo(s)`
          : "Sin webhooks",
    },
  };

  const res = NextResponse.json(status);
  res.headers.set("cache-control", "no-store");
  return res;
}
