import { NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_AURA_BACKEND_URL || "http://localhost:8000";

export async function GET() {
  try {
    const headers: HeadersInit = { "Content-Type": "application/json" };
    const apiKey = process.env.AURA_API_KEY;
    if (apiKey) headers["X-API-Key"] = apiKey;

    const response = await fetch(`${BACKEND_URL}/api/system/telemetry`, {
      headers,
      cache: "no-store",
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend telemetry error: ${response.status}` },
        { status: response.status },
      );
    }

    return NextResponse.json(await response.json());
  } catch (error: unknown) {
    console.error("Error fetching system telemetry:", error);
    return NextResponse.json({ error: "Telemetry unavailable" }, { status: 503 });
  }
}
