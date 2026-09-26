export interface NomadServiceHealth {
  service: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  port: number;
  last_check: string;
  error?: string;
  latency_ms?: number;
}

export interface NomadStatusResponse {
  status: string;
  healthy: string[];
  degraded: string[];
  down: string[];
  total_services: number;
  services: Record<string, NomadServiceHealth>;
}

export interface RagQueryResponse {
  query: string;
  context: string;
  sources: Array<{
    id: string;
    score: number;
    text: string;
  }>;
  total_sources: number;
}

export interface RagIngestResponse {
  document_id: string;
  status: string;
  ollama: number[];
  qdrant: Record<string, unknown>;
}
