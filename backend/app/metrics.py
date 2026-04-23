"""
Metrics Collection Middleware.
Collects and exposes application metrics for observability.
"""

import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import Request


@dataclass
class MetricPoint:
    """Single metric data point."""

    timestamp: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    Thread-safe metrics collector.

    Tracks:
    - Request latency (p50, p95, p99)
    - Request counts by endpoint and status
    - Cache hit/miss rates
    - Database query times
    - Quality scores over time
    """

    _instance: Optional["MetricsCollector"] = None
    _lock = threading.Lock()
    _initialized: bool

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._lock = threading.Lock()
        self._initialized = True

        # Rolling windows for latency tracking (last 1000 requests)
        self._latencies: deque[float] = deque(maxlen=1000)

        # Counters
        self._request_counts: dict[str, int] = {}
        self._status_counts: dict[int, int] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._db_queries = 0
        self._db_total_time_ms = 0.0

        # Recent quality scores (last 100)
        self._quality_scores: deque[dict[str, Any]] = deque(maxlen=100)

        # Anomaly detection stats
        self._anomalies_detected = 0
        self._high_risk_alerts = 0

        # Start time for uptime
        self._start_time = datetime.now(UTC)

    def record_request(self, path: str, method: str, status_code: int, duration_ms: float) -> None:
        """Record an API request metric."""
        with self._lock:
            # Latency
            self._latencies.append(duration_ms)

            # Request count by path
            key = f"{method}:{path}"
            self._request_counts[key] = self._request_counts.get(key, 0) + 1

            # Status code distribution
            self._status_counts[status_code] = self._status_counts.get(status_code, 0) + 1

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        with self._lock:
            self._cache_misses += 1

    def record_db_query(self, duration_ms: float) -> None:
        """Record a database query."""
        with self._lock:
            self._db_queries += 1
            self._db_total_time_ms += duration_ms

    def record_quality_score(self, cdk: str, score: float) -> None:
        """Record a quality score measurement."""
        with self._lock:
            self._quality_scores.append({"timestamp": datetime.now(UTC).isoformat(), "cdk": cdk, "score": score})

    def record_anomaly(self, is_high_risk: bool = False) -> None:
        """Record an anomaly detection."""
        with self._lock:
            self._anomalies_detected += 1
            if is_high_risk:
                self._high_risk_alerts += 1

    def get_latency_percentiles(self) -> dict[str, float]:
        """Calculate latency percentiles."""
        with self._lock:
            if not self._latencies:
                return {"p50": 0, "p95": 0, "p99": 0, "avg": 0}

            sorted_latencies = sorted(self._latencies)
            n = len(sorted_latencies)

            return {
                "p50": sorted_latencies[int(n * 0.5)] if n > 0 else 0,
                "p95": sorted_latencies[int(n * 0.95)] if n > 0 else 0,
                "p99": sorted_latencies[int(n * 0.99)] if n > 0 else 0,
                "avg": sum(sorted_latencies) / n if n > 0 else 0,
            }

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache hit/miss statistics."""
        with self._lock:
            total = self._cache_hits + self._cache_misses
            hit_rate = self._cache_hits / total if total > 0 else 0

            return {
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "total": total,
                "hit_rate": round(hit_rate, 3),
            }

    def get_db_stats(self) -> dict[str, Any]:
        """Get database query statistics."""
        with self._lock:
            avg_time = self._db_total_time_ms / self._db_queries if self._db_queries > 0 else 0

            return {
                "total_queries": self._db_queries,
                "total_time_ms": round(self._db_total_time_ms, 2),
                "avg_query_time_ms": round(avg_time, 2),
            }

    def get_quality_stats(self) -> dict[str, Any]:
        """Get quality score statistics."""
        with self._lock:
            if not self._quality_scores:
                return {"avg_score": 0, "measurements": 0, "recent": []}

            scores = [q["score"] for q in self._quality_scores]

            return {
                "avg_score": round(sum(scores) / len(scores), 3),
                "measurements": len(scores),
                "recent": list(self._quality_scores)[-5:],
            }

    def get_anomaly_stats(self) -> dict[str, int]:
        """Get anomaly detection statistics."""
        with self._lock:
            return {"total_detected": self._anomalies_detected, "high_risk_alerts": self._high_risk_alerts}

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all metrics as a combined report."""
        uptime = (datetime.now(UTC) - self._start_time).total_seconds()

        with self._lock:
            total_requests = sum(self._request_counts.values())

        return {
            "uptime_seconds": round(uptime, 2),
            "total_requests": total_requests,
            "latency": self.get_latency_percentiles(),
            "cache": self.get_cache_stats(),
            "database": self.get_db_stats(),
            "quality_scores": self.get_quality_stats(),
            "anomalies": self.get_anomaly_stats(),
            "status_distribution": dict(self._status_counts),
            "top_endpoints": self._get_top_endpoints(10),
        }

    def _get_top_endpoints(self, n: int) -> list:
        """Get top N most-called endpoints."""
        sorted_endpoints = sorted(self._request_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"endpoint": k, "count": v} for k, v in sorted_endpoints[:n]]

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            self._latencies.clear()
            self._request_counts.clear()
            self._status_counts.clear()
            self._cache_hits = 0
            self._cache_misses = 0
            self._db_queries = 0
            self._db_total_time_ms = 0.0
            self._quality_scores.clear()
            self._anomalies_detected = 0
            self._high_risk_alerts = 0
            self._start_time = datetime.now(UTC)


# Global metrics instance
metrics = MetricsCollector()


@contextmanager
def timed_db_query():
    """Context manager to track database query time."""
    start = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start) * 1000
        metrics.record_db_query(duration_ms)


async def metrics_middleware(request: Request, call_next):
    """FastAPI middleware to collect request metrics."""
    start_time = time.time()

    response = await call_next(request)

    duration_ms = (time.time() - start_time) * 1000

    # Record the request
    metrics.record_request(
        path=request.url.path, method=request.method, status_code=response.status_code, duration_ms=duration_ms
    )

    return response
