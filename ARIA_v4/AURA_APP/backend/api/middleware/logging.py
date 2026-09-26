"""Logging Middleware"""

from datetime import datetime
from typing import Dict, List


class LoggingMiddleware:
    """Middleware de logging de requests"""

    def __init__(self):
        self.logs: List[Dict] = []

    def log_request(self, method: str, path: str, status: int = 200) -> None:
        log = {
            'timestamp': datetime.now().isoformat(),
            'method': method,
            'path': path,
            'status': status,
        }
        self.logs.append(log)

    def get_logs(self, limit: int = 100) -> List[Dict]:
        return self.logs[-limit:]

    def clear(self) -> None:
        self.logs.clear()
