import { NextRequest, NextResponse } from "next/server";

/**
 * GET /api/mobile/story?session_id={sessionId}
 *
 * Mobile-optimized gateway to query the literary context bound to an AME session.
 *
 * Delegates to the existing backend endpoint:
 *   GET /api/mobile/story/context/{session_id}
 *
 * Returns the active work_id and character_id (or null when no context is bound).
 * Uses the internal server-side proxy, so credentials are never exposed to the client.
 */

interface MobileStoryContext {
  active: boolean;
  work_id: string | null;
  character_id: string | null;
  work_title?: string;
  character_name?: string;
}

export async function GET(request: NextRequest) {
  try {
    const url = new URL(request.url);
    const sessionId = url.searchParams.get("session_id") || "";

    if (!sessionId.trim()) {
      return NextResponse.json(
        { status: "no_context", active: false, context: null },
        { status: 200 }
      );
    }

    const origin = new URL(request.url).origin;

    try {
      const response = await fetch(
        `${origin}/api/mobile/story/context/${encodeURIComponent(sessionId.trim())}`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
          signal: AbortSignal.timeout(5000),
        }
      );

      if (response.ok) {
        const data = await response.json() as MobileStoryContext;
        return NextResponse.json(data, { status: 200 });
      }

      if (response.status === 401) {
        return NextResponse.json({ error: "Backend authentication failed" }, { status: 401 });
      }

      return NextResponse.json(
        { status: "no_context", active: false, context: null },
        { status: 200 }
      );
    } catch {
      return NextResponse.json(
        { status: "no_context", active: false, context: null },
        { status: 200 }
      );
    }
  } catch (error: unknown) {
    console.error("Mobile story API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch story context" },
      { status: 500 }
    );
  }
}
