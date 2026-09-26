from prometheus_client import Counter, Gauge, Histogram, start_http_server

websocket_connections = Counter(
    "aura_websocket_connections_total",
    "Total WebSocket connections",
    ["endpoint"],
)
api_requests = Counter(
    "aura_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)
active_agents = Gauge("aura_active_agents", "Number of active agents")
system_cpu_percent = Gauge("aura_system_cpu_percent", "System CPU usage percentage")
system_memory_percent = Gauge("aura_system_memory_percent", "System memory usage percentage")
request_duration = Histogram(
    "aura_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
)


def init_metrics_server(port: int = 8001) -> None:
    start_http_server(port)
