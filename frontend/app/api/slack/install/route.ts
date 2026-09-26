import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET() {
  const clientId = process.env.SLACK_CLIENT_ID;
  const scopes = ["commands", "chat:write", "app_mentions:read"];

  if (!clientId) {
    return NextResponse.json({ error: "SLACK_CLIENT_ID not configured" }, { status: 500 });
  }

  const installUrl = new URL("https://slack.com/oauth/v2/authorize");
  installUrl.searchParams.set("client_id", clientId);
  installUrl.searchParams.set("scope", scopes.join(","));
  installUrl.searchParams.set("redirect_uri", process.env.SLACK_REDIRECT_URI || "");

  return NextResponse.redirect(installUrl.toString());
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.text();
    const payload = JSON.parse(body);

    if (payload.code) {
      return NextResponse.json({
        ok: true,
        message: "Installation code received",
        code: payload.code,
      });
    }

    return NextResponse.json({ ok: true, message: "Slack app installed" });
  } catch (error) {
    console.error("Slack install error:", error);
    return NextResponse.json({ error: "Installation failed" }, { status: 500 });
  }
}
