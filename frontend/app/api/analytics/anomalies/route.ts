import { NextResponse } from "next/server";
import { generateFallbackAnalytics } from "@/lib/analyticsFallback";

/**
 * GET /api/analytics/anomalies
 * Returns detected anomalies.
 */
export async function GET() {
  const analytics = generateFallbackAnalytics();
  return NextResponse.json(analytics.anomalies);
}
