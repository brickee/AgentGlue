"""Tool call deduplication middleware.

Intercepts tool calls and returns cached results when the same tool
has been called with the same arguments.
"""

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class CacheEntry:
    result: Any
    created_at: float
    ttl: float
    tool_name: str
    args_hash: str
    agent_id: str

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl

    @property
    def age(self) -> float:
        return time.monotonic() - self.created_at


class ToolDedup:
    """Deduplicates tool calls across multiple agents.

    v0.1 intentionally stays narrow: exact-match dedup via a stable hash of
    tool name + serialized args/kwargs with TTL-based caching.
    """

    def __init__(self, default_ttl: float = 300.0):
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def _make_key(self, tool_name: str, args: tuple, kwargs: dict) -> str:
        raw = json.dumps({"tool": tool_name, "args": list(args), "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def lookup(self, tool_name: str, args: tuple, kwargs: dict) -> Optional[CacheEntry]:
        key = self._make_key(tool_name, args, kwargs)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.expired:
                del self._cache[key]
                return None
            return entry

    def store(
        self,
        tool_name: str,
        args: tuple,
        kwargs: dict,
        result: Any,
        agent_id: str = "",
        ttl: float | None = None,
    ) -> None:
        key = self._make_key(tool_name, args, kwargs)
        entry = CacheEntry(
            result=result,
            created_at=time.monotonic(),
            ttl=self.default_ttl if ttl is None else ttl,
            tool_name=tool_name,
            args_hash=key,
            agent_id=agent_id,
        )
        with self._lock:
            self._cache[key] = entry

    def invalidate(self, tool_name: str, args: tuple = (), kwargs: dict | None = None) -> bool:
        key = self._make_key(tool_name, args, kwargs or {})
        with self._lock:
            return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        with self._lock:
            live_keys = [k for k, v in self._cache.items() if not v.expired]
            stale_keys = [k for k, v in self._cache.items() if v.expired]
            for k in stale_keys:
                del self._cache[k]
            return len(live_keys)

    def wrap(
        self,
        func: Callable,
        tool_name: str | None = None,
        ttl: float | None = None,
    ) -> Callable:
        """Wrap a tool function with dedup logic."""
        name = tool_name or func.__name__

        def wrapper(*args, **kwargs):
            entry = self.lookup(name, args, kwargs)
            if entry is not None:
                return entry.result

            result = func(*args, **kwargs)
            self.store(name, args, kwargs, result, ttl=ttl)
            return result

        wrapper.__name__ = func.__name__
        wrapper.__wrapped__ = func
        return wrapper
