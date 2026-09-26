export interface AnalyticsSummary {
  total_events_today: number;
  total_errors: number;
  avg_latency_ms: number;
  integrations_connected: number;
  uptime_percent: number;
}

export interface IntegrationMetrics {
  events: number;
  errors: number;
  latency: number;
  uptime: number;
}

export interface TrendData {
  week_over_week: number;
  month_over_month: number;
  anomalies: Array<{
    date: string;
    type: string;
    severity: string;
    value: number;
    threshold: number;
  }>;
  trend: string;
  total_events_7d: number;
  total_events_30d: number;
}

export interface ForecastData {
  next_7_days: number[];
  confidence: number;
  method: string;
  historical_avg: number;
  historical_trend: number;
  generated_at: string;
}

export interface AnalyticsResponse {
  summary: AnalyticsSummary;
  by_integration: Record<string, IntegrationMetrics>;
  trends: TrendData;
  forecast: ForecastData;
  anomalies: Array<Record<string, unknown>>;
}

/**
 * Generate fallback analytics data when backend is unavailable.
 */
export function generateFallbackAnalytics(): AnalyticsResponse {
  const now = new Date();

  return {
    summary: {
      total_events_today: 1234,
      total_errors: 3,
      avg_latency_ms: 145,
      integrations_connected: 5,
      uptime_percent: 99.9,
    },
    by_integration: {
      slack: { events: 300, errors: 0, latency: 120, uptime: 100 },
      discord: { events: 250, errors: 1, latency: 130, uptime: 99.6 },
      telegram: { events: 200, errors: 0, latency: 110, uptime: 100 },
      teams: { events: 180, errors: 1, latency: 150, uptime: 99.4 },
      webhook: { events: 304, errors: 1, latency: 200, uptime: 99.7 },
    },
    trends: {
      week_over_week: 12.5,
      month_over_month: 8.3,
      anomalies: [],
      trend: "growing",
      total_events_7d: 8450,
      total_events_30d: 35200,
    },
    forecast: {
      next_7_days: [1250, 1280, 1220, 1300, 1270, 1320, 1290],
      confidence: 0.85,
      method: "moving_average_with_trend",
      historical_avg: 1175,
      historical_trend: 5.2,
      generated_at: now.toISOString(),
    },
    anomalies: [],
  };
}
