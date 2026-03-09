"""Shared memory store for cross-agent knowledge sharing.

Allows agents to publish discoveries and read each other's findings,
reducing redundant tool calls and enabling collaborative workflows.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryEntry:
    key: str
    value: Any
    agent_id: str
    created_at: float = field(default_factory=time.monotonic)
    ttl: float = 600.0  # default 10 minutes
    confidence: float = 1.0
    scope: str = "shared"  # private | shared | team

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl

    @property
    def age(self) -> float:
        return time.monotonic() - self.created_at


class SharedMemory:
    """Thread-safe shared memory for multi-agent knowledge.

    Features:
    - TTL-based expiration
    - Confidence scores (decay over time optional)
    - Scope control: private (single agent), shared (all agents), team (group)
    - Staleness detection
    """

    def __init__(self, default_ttl: float = 600.0, min_confidence: float = 0.0):
        self.default_ttl = default_ttl
        self.min_confidence = min_confidence
        self._store: Dict[str, MemoryEntry] = {}
        self._lock = threading.Lock()

    def write(
        self,
        key: str,
        value: Any,
        agent_id: str = "",
        ttl: float | None = None,
        confidence: float = 1.0,
        scope: str = "shared",
    ) -> None:
        entry = MemoryEntry(
            key=key,
            value=value,
            agent_id=agent_id,
            ttl=ttl or self.default_ttl,
            confidence=confidence,
            scope=scope,
        )
        with self._lock:
            self._store[key] = entry

    def read(
        self,
        key: str,
        agent_id: str = "",
        min_confidence: float | None = None,
    ) -> Optional[Any]:
        threshold = min_confidence if min_confidence is not None else self.min_confidence
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expired:
                del self._store[key]
                return None
            if entry.confidence < threshold:
                return None
            if entry.scope == "private" and entry.agent_id != agent_id:
                return None
            return entry.value

    def read_entry(self, key: str, agent_id: str = "") -> Optional[MemoryEntry]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expired:
                del self._store[key]
                return None
            if entry.scope == "private" and entry.agent_id != agent_id:
                return None
            return entry

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def keys(self, agent_id: str = "", scope: str | None = None) -> List[str]:
        with self._lock:
            result = []
            for k, entry in self._store.items():
                if entry.expired:
                    continue
                if entry.scope == "private" and entry.agent_id != agent_id:
                    continue
                if scope and entry.scope != scope:
                    continue
                result.append(k)
            return result

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return sum(1 for e in self._store.values() if not e.expired)
