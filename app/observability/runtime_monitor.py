from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from time import monotonic
from typing import Any


@dataclass(frozen=True)
class TimedScope:
    name: str
    started_at: float


class RuntimeMonitor:
    def __init__(self) -> None:
        self._counters: Counter[str] = Counter()
        self._latency_samples: dict[str, list[float]] = {}
        self._logs: deque[dict[str, Any]] = deque(maxlen=200)

    def reset(self) -> None:
        self._counters.clear()
        self._latency_samples.clear()
        self._logs.clear()

    def start_timer(self, name: str) -> TimedScope:
        return TimedScope(name=name, started_at=monotonic())

    def stop_timer(self, scope: TimedScope) -> float:
        elapsed_ms = round((monotonic() - scope.started_at) * 1000.0, 3)
        self._latency_samples.setdefault(scope.name, []).append(elapsed_ms)
        return elapsed_ms

    def increment(self, metric_key: str, delta: int = 1) -> None:
        self._counters[metric_key] += delta

    def log(self, payload: dict[str, Any]) -> None:
        self._logs.append(payload)

    def snapshot(self) -> dict[str, Any]:
        latencies = {}
        for key, values in self._latency_samples.items():
            if not values:
                continue
            sorted_values = sorted(values)
            idx = min(len(sorted_values) - 1, int(0.95 * (len(sorted_values) - 1)))
            latencies[key] = {
                "count": len(values),
                "avg_ms": round(sum(values) / len(values), 3),
                "p95_ms": sorted_values[idx],
            }
        return {
            "counters": dict(self._counters),
            "latencies": latencies,
            "recent_logs": list(self._logs),
        }


RUNTIME_MONITOR = RuntimeMonitor()
