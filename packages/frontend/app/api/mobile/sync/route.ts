import { NextRequest, NextResponse } from "next/server";

/**
 * PUT /api/mobile/sync
 * Sync offline changes with the server.
 * Phase 58 - Option A: Mobile API - Sync mechanism
 */

const MOCK_CHANGES = [
  {
    type: "message",
    data: {
      id: "sync_msg_1",
      ameId: "ame_core",
      role: "ame" as const,
      content: "Welcome back! I've synced your offline messages.",
      timestamp: new Date().toISOString(),
    },
  },
  {
    type: "ame_status",
    data: {
      id: "ame_core",
      status: "online" as const,
    },
  },
];

type SyncRequestBody = {
  lastSync?: string;
};

export async function PUT(request: NextRequest) {
  try {
    const body = (await request.json()) as SyncRequestBody;
    const { lastSync } = body;

    if (!lastSync) {
      return NextResponse.json(
        { error: "lastSync timestamp is required" },
        { status: 400 }
      );
    }

    // In production, fetch from backend
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    const apiKey = process.env.AURA_API_KEY || "";

    try {
      const response = await fetch(`${backendUrl}/api/mobile/sync`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify({ lastSync }),
        signal: AbortSignal.timeout(5000),
      });

      if (response.ok) {
        const data = await response.json();
        return NextResponse.json(data);
      }

      if (response.status === 401) {
        return NextResponse.json({ error: "Backend authentication failed" }, { status: 401 });
      }
      if (response.status === 404) {
        return NextResponse.json({ error: "Backend sync endpoint not found" }, { status: 404 });
      }
    } catch {
      console.warn("Backend unavailable, using fallback sync data");
    }

    // Parse the lastSync to determine if there are changes
    const lastSyncDate = new Date(lastSync);
    const now = new Date();
    const hoursSinceSync = (now.getTime() - lastSyncDate.getTime()) / 3600000;

    // Return changes if more than 1 hour since last sync
    const changes = hoursSinceSync > 1 ? MOCK_CHANGES : [];

    return NextResponse.json({
      changes,
      newLastSync: now.toISOString(),
    });
  } catch (error) {
    console.error("Mobile sync API error:", error);
    return NextResponse.json(
      { error: "Failed to sync" },
      { status: 500 }
    );
  }
}