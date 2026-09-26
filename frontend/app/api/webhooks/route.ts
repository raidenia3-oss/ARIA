import { NextRequest, NextResponse } from "next/server";
import { WebhookManager } from "../../../lib/webhook-manager";
import logger from "../../../lib/logger";
import { requireAuth } from "../../../lib/requireAuth";

export const runtime = "nodejs";

function isBlockedUrl(urlStr: string): boolean {
  let u: URL;
  try {
    u = new URL(urlStr);
  } catch {
    return true;
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") return true;
  const host = u.hostname.toLowerCase();
  if (
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "0.0.0.0" ||
    host === "::1" ||
    host.endsWith(".localhost") ||
    host.endsWith(".local")
  ) {
    return true;
  }
  if (/^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.)/.test(host)) {
    return true;
  }
  return false;
}

export async function GET(request: NextRequest) {
  const auth = requireAuth(request);
  if (auth) return auth;

  const url = new URL(request.url);
  const action = url.searchParams.get("action");

  logger.api("GET", "/api/webhooks", 0, 200);

  if (action === "list") {
    return NextResponse.json({ webhooks: WebhookManager.getAll() });
  }

  return NextResponse.json({
    webhooks: WebhookManager.getAll(),
    documentation: {
      register: "POST /api/webhooks with { id, url, events }",
      unregister: "DELETE /api/webhooks?id=<id>",
      trigger: "POST /api/webhooks/trigger with { event, data }",
    },
  });
}

export async function POST(request: NextRequest) {
  const auth = requireAuth(request);
  if (auth) return auth;

  try {
    const body = (await request.json()) as {
      id?: string;
      url?: string;
      events?: string[];
      event?: string;
      data?: unknown;
    };

    if (body.id && body.url && body.events) {
      if (isBlockedUrl(body.url)) {
        logger.warn("webhooks", "blocked private/loopback url", {
          url: body.url,
        });
        return NextResponse.json(
          { error: "URL not allowed (private or loopback address)" },
          { status: 400 },
        );
      }
      const result = WebhookManager.register(body.id, body.url, body.events);
      logger.event("webhook registered", {
        id: body.id,
        url: body.url,
        events: body.events,
      });
      return NextResponse.json({ success: true, webhook: result });
    }

    if (body.event && body.data) {
      const results = await WebhookManager.trigger(body.event, body.data);
      logger.event("webhook triggered", { event: body.event });
      return NextResponse.json({ success: true, results });
    }

    logger.warn("webhooks", "invalid payload", {
      id: body.id,
      event: body.event,
    });
    return NextResponse.json(
      {
        error:
          "Invalid payload. Expected { id, url, events } or { event, data }",
      },
      { status: 400 },
    );
  } catch (error) {
    logger.error("webhooks", "POST failed", error);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}

export async function DELETE(request: NextRequest) {
  const auth = requireAuth(request);
  if (auth) return auth;

  try {
    const url = new URL(request.url);
    const id = url.searchParams.get("id");

    if (!id) {
      return NextResponse.json(
        { error: "Missing id parameter" },
        { status: 400 },
      );
    }

    const result = WebhookManager.unregister(id);
    return NextResponse.json({ success: true, result });
  } catch (error) {
    logger.error("webhooks", "DELETE failed", error);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
