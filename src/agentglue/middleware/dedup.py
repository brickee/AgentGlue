"""Tool call deduplication middleware.

Intercepts tool calls and returns cached results when the same tool
has been called with the same (or semantically similar) arguments.
"""

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class CacheEntry:
    result: Any
    created_at: float
    ttl: float
    tool_name: str
    args_hash: str
    agent_id: str  # who originally made the call

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl


class ToolDedup:
    """Deduplicates tool calls across multiple agents.

    Supports exact-match dedup (hash of tool name + serialized args) and
    optional semantic dedup (embedding similarity, planned for v0.2).
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
            ttl=ttl or self.default_ttl,
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
            return len(self._cache)

    def wrap(
        self,
        func: Callable,
        tool_name: str | None = None,
        ttl: float | None = None,
    ) -> Callable:
        """Wrap a tool function with dedup logic."""
        name = tool_name or func.__name__

        def wrapper(*args, **kwargs):
            # Check cache
            entry = self.lookup(name, args, kwargs)
            if entry is not None:
                return entry.result

            # Call the real tool
            result = func(*args, **kwargs)

            # Store result
            self.store(name, args, kwargs, result, ttl=ttl)

            return result

        wrapper.__name__ = func.__name__
        wrapper.__wrapped__ = func
        return wrapper
