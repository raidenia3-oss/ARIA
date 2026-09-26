import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET() {
  const teamsConfig = {
    manifestUrl: "/teams/manifest.json",
    capabilities: ["Tab", "Bot", "MessagingExtension"],
    supportedPlatforms: ["desktop", "mobile", "web"],
  };

  return NextResponse.json({
    status: "Teams integration ready",
    config: teamsConfig,
  });
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as { type?: string };

    if (body.type === "message") {
      return NextResponse.json({
        type: "message",
        text: "🤖 AME Assistant is ready",
      });
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("Teams endpoint error:", error);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
