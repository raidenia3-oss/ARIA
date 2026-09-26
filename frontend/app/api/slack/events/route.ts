import { NextRequest, NextResponse } from "next/server";
import { getApp } from "../../../../lib/slack-bot";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  try {
    const slackApp = await getApp();
    const body = await request.text();
    const payload = JSON.parse(body);

    if (payload.type === "url_verification") {
      return NextResponse.json({ challenge: payload.challenge });
    }

    if (slackApp) {
      await slackApp.processEvent(payload);
    } else {
      return NextResponse.json({ ok: true, message: "Slack app not configured (mock response)" });
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("Slack events error:", error);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
