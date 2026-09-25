import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional


class DistributedTracing:
    def __init__(self) -> None:
        self._traces: Dict[str, Dict[str, Any]] = {}
        self._spans: List[Dict[str, Any]] = []

    async def trace_request(self, operation: str, context: Optional[Dict[str, Any]] = None) -> str:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        self._traces[trace_id] = {
            "trace_id": trace_id,
            "operation": operation,
            "context": context or {},
            "started_at": time.time(),
            "spans": [],
            "completed": False,
        }
        return trace_id

    async def add_span(
        self, trace_id: str, name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        if trace_id in self._traces:
            span = {
                "span_id": str(uuid.uuid4()),
                "trace_id": trace_id,
                "name": name,
                "metadata": metadata or {},
                "started_at": time.time(),
            }
            self._traces[trace_id]["spans"].append(span)
            self._spans.append(span)

    async def complete_trace(self, trace_id: str, result: Optional[Any] = None) -> Dict[str, Any]:
        if trace_id in self._traces:
            trace = self._traces[trace_id]
            trace["completed"] = True
            trace["ended_at"] = time.time()
            trace["duration"] = trace["ended_at"] - trace["started_at"]
            trace["result"] = result
            return trace
        return {"error": "trace not found"}

    async def get_bottlenecks(self) -> List[Dict[str, Any]]:
        bottlenecks = []
        for trace in self._traces.values():
            if trace.get("duration", 0) > 5.0:
                bottlenecks.append(
                    {
                        "trace_id": trace["trace_id"],
                        "operation": trace["operation"],
                        "duration": trace["duration"],
                    }
                )
        return sorted(bottlenecks, key=lambda x: x["duration"], reverse=True)[:10]
