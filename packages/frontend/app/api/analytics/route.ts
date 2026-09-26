import { NextResponse } from "next/server";
import { generateFallbackAnalytics, type AnalyticsResponse } from "@/lib/analyticsFallback";

/**
 * GET /api/analytics
 * 
 * Returns aggregated analytics data including summary, per-integration metrics,
 * trends, anomalies, and forecasts.
 * Phase 58 - Option F3: Analytics Endpoints
 */

export async function GET() {
  try {
    // Try to get data from the analytics engine output
    const analyticsData = await fetchAnalyticsData();
    
    return NextResponse.json(analyticsData);
  } catch (error) {
    console.error("Analytics API error:", error);
    
    // Return fallback data if analytics engine is unavailable
    return NextResponse.json(generateFallbackAnalytics());
  }
}

/**
 * Fetch analytics data from the analytics engine output files.
 */
async function fetchAnalyticsData(): Promise<AnalyticsResponse> {
  try {
    // Try to read from the analytics engine output
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    const response = await fetch(`${backendUrl}/api/analytics`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(5000),
    });

    if (response.ok) {
      return await response.json();
    }
  } catch {
    console.warn("Backend analytics unavailable, using fallback data");
  }

  return generateFallbackAnalytics();
}

