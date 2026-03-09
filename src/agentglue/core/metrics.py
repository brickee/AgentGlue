"""Runtime metrics collection for AgentGlue.

Tracks coordination efficiency: dedup hits, cache hits, rate limit
interventions, conflicts prevented, etc.
"""

import threading
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class GlueMetrics:
    """Aggregate metrics for an AgentGlue session."""

    tool_calls_total: int = 0
    tool_calls_deduped: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    rate_limit_interventions: int = 0
    rate_limit_wait_time_ms: float = 0.0
    shared_memory_writes: int = 0
    shared_memory_reads: int = 0
    shared_memory_hits: int = 0
    shared_memory_misses: int = 0
    shared_memory_stale: int = 0
    task_conflicts_detected: int = 0
    task_conflicts_prevented: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_tool_call(self, deduped: bool = False, cache_hit: bool = False) -> None:
        with self._lock:
            self.tool_calls_total += 1
            if deduped:
                self.tool_calls_deduped += 1
            if cache_hit:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

    def record_rate_limit(self, wait_ms: float = 0.0) -> None:
        with self._lock:
            self.rate_limit_interventions += 1
            self.rate_limit_wait_time_ms += wait_ms

    def record_memory_access(self, hit: bool, stale: bool = False) -> None:
        with self._lock:
            self.shared_memory_reads += 1
            if hit and not stale:
                self.shared_memory_hits += 1
            elif stale:
                self.shared_memory_stale += 1
            else:
                self.shared_memory_misses += 1

    def record_conflict(self, prevented: bool = True) -> None:
        with self._lock:
            self.task_conflicts_detected += 1
            if prevented:
                self.task_conflicts_prevented += 1

    @property
    def dedup_rate(self) -> float:
        if self.tool_calls_total == 0:
            return 0.0
        return self.tool_calls_deduped / self.tool_calls_total

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total

    def summary(self) -> Dict:
        return {
            "tool_calls_total": self.tool_calls_total,
            "tool_calls_deduped": self.tool_calls_deduped,
            "dedup_rate": f"{self.dedup_rate:.1%}",
            "cache_hit_rate": f"{self.cache_hit_rate:.1%}",
            "rate_limit_interventions": self.rate_limit_interventions,
            "shared_memory_hits": self.shared_memory_hits,
            "task_conflicts_prevented": self.task_conflicts_prevented,
        }

    def report(self) -> str:
        lines = [
            "AgentGlue Report:",
            f"  Tool calls total:         {self.tool_calls_total}",
            f"  Tool calls saved by dedup: {self.tool_calls_deduped}/{self.tool_calls_total} ({self.dedup_rate:.0%})",
            f"  Cache hit rate:           {self.cache_hit_rate:.0%}",
            f"  Rate limit interventions: {self.rate_limit_interventions}",
            f"  Shared memory hits:       {self.shared_memory_hits}",
            f"  Task conflicts prevented: {self.task_conflicts_prevented}",
        ]
        return "\n".join(lines)
