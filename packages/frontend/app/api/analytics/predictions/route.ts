import { NextResponse } from "next/server";
import { generateFallbackAnalytics } from "@/lib/analyticsFallback";

/**
 * GET /api/analytics/predictions
 * Returns forecast predictions for the next 7 days.
 */
export async function GET() {
  const analytics = generateFallbackAnalytics();
  return NextResponse.json(analytics.forecast);
}
