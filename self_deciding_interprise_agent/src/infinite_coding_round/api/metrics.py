"""In-memory, process-local observability metrics for the /ask endpoint.

Deliberately simple (no external time-series DB) -- this exists to make the agent's
runtime characteristics visible via /stats for demo/portfolio purposes, not as a
production metrics pipeline. Resets on process restart.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class _Metrics:
    total_queries: int = 0
    total_latency_ms: float = 0.0
    total_confidence: float = 0.0
    total_retries: int = 0
    total_validation_passed: int = 0
    route_counts: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, *, route: str, latency_ms: float, confidence: float, retry_count: int, validation_passed: bool) -> None:
        with self._lock:
            self.total_queries += 1
            self.total_latency_ms += latency_ms
            self.total_confidence += confidence
            self.total_retries += 1 if retry_count > 0 else 0
            self.total_validation_passed += 1 if validation_passed else 0
            self.route_counts[route] = self.route_counts.get(route, 0) + 1

    def snapshot(self) -> dict:
        with self._lock:
            n = self.total_queries or 1
            return {
                "total_queries": self.total_queries,
                "avg_latency_ms": round(self.total_latency_ms / n, 1),
                "avg_confidence": round(self.total_confidence / n, 3),
                "retry_rate": round(self.total_retries / n, 3),
                "validation_pass_rate": round(self.total_validation_passed / n, 3),
                "route_counts": dict(self.route_counts),
            }


metrics = _Metrics()
