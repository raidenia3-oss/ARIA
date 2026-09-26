"""Headroom Optimizer — Comprime tokens (Repositorio #1)"""

import json
from typing import Any, List


class HeadroomOptimizer:
    """Integra Headroom - comprime logs para menos tokens"""

    def __init__(self):
        self.compression_ratio = 0.0

    def compress_logs(self, logs: List[dict]) -> str:
        """Comprime logs antes de enviar a LLM"""
        if not logs:
            return ""

        summary = f"[{len(logs)} events: "

        types = {}
        for log in logs:
            log_type = log.get('type', 'unknown')
            types[log_type] = types.get(log_type, 0) + 1

        summary += ", ".join([f"{k}:{v}" for k, v in types.items()])
        summary += "]"

        self.compression_ratio = len(summary) / max(len(str(logs)), 1)
        return summary

    def optimize_context(self, context: dict) -> dict:
        """Optimiza contexto para LLM"""
        essential_fields = ['user_input', 'last_intent', 'user_profile']

        optimized = {}
        for field in essential_fields:
            if field in context:
                optimized[field] = context[field]

        return optimized


if __name__ == '__main__':
    opt = HeadroomOptimizer()
    logs = [
        {'type': 'chat', 'text': 'hello'},
        {'type': 'action', 'text': 'execute skill'},
    ]
    compressed = opt.compress_logs(logs)
    print(f"Compressed: {compressed}")
    print(f"Ratio: {opt.compression_ratio:.2%}")
