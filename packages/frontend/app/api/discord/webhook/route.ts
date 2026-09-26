import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as { type?: number };

    if (body.type === 1) {
      return NextResponse.json({ type: 1 });
    }

    if (body.type === 2) {
      return NextResponse.json({
        type: 4,
        data: {
          content: "🤖 AME Assistant received your request.",
          embeds: [
            {
              title: "AME Assistant",
              description: "Ready to assist",
              color: 0xDC143C,
            },
          ],
        },
      });
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("Discord webhook error:", error);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({ status: "Discord webhook endpoint active" });
}
