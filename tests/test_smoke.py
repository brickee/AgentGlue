"""Smoke tests for AgentGlue core functionality."""

import time
from agentglue import AgentGlue
from agentglue.middleware.dedup import ToolDedup
from agentglue.middleware.shared_memory import SharedMemory
from agentglue.middleware.task_lock import TaskLock
from agentglue.core.allocator import RateLimiter, TokenBucket
from agentglue.core.metrics import GlueMetrics


def test_dedup_exact_match():
    """Same tool + same args = cache hit."""
    dedup = ToolDedup(default_ttl=60.0)
    call_count = 0

    def search(query):
        nonlocal call_count
        call_count += 1
        return f"result for {query}"

    wrapped = dedup.wrap(search)

    r1 = wrapped("transformers")
    r2 = wrapped("transformers")  # should be deduped
    r3 = wrapped("attention")    # different args, should call

    assert r1 == r2 == "result for transformers"
    assert r3 == "result for attention"
    assert call_count == 2  # only 2 real calls, not 3


def test_dedup_ttl_expiry():
    """Cache entries expire after TTL."""
    dedup = ToolDedup(default_ttl=0.1)  # 100ms TTL
    call_count = 0

    def search(query):
        nonlocal call_count
        call_count += 1
        return f"result-{call_count}"

    wrapped = dedup.wrap(search)
    r1 = wrapped("test")
    time.sleep(0.15)
    r2 = wrapped("test")  # should re-call after TTL

    assert r1 == "result-1"
    assert r2 == "result-2"
    assert call_count == 2


def test_shared_memory_basic():
    """Write and read shared memory."""
    mem = SharedMemory()
    mem.write("key1", "value1", agent_id="agent-a")
    assert mem.read("key1", agent_id="agent-b") == "value1"


def test_shared_memory_private_scope():
    """Private memory is only visible to the writer."""
    mem = SharedMemory()
    mem.write("secret", "data", agent_id="agent-a", scope="private")
    assert mem.read("secret", agent_id="agent-a") == "data"
    assert mem.read("secret", agent_id="agent-b") is None


def test_shared_memory_confidence():
    """Low confidence entries are filtered."""
    mem = SharedMemory(min_confidence=0.5)
    mem.write("key", "value", confidence=0.3)
    assert mem.read("key") is None
    mem.write("key2", "value2", confidence=0.8)
    assert mem.read("key2") == "value2"


def test_task_lock_basic():
    """Task locking prevents conflicts."""
    lock = TaskLock()
    ok1, _ = lock.acquire("task-1", "agent-a")
    ok2, reason = lock.acquire("task-1", "agent-b")

    assert ok1 is True
    assert ok2 is False
    assert "conflict" in reason

    lock.release("task-1", "agent-a")
    ok3, _ = lock.acquire("task-1", "agent-b")
    assert ok3 is True


def test_task_lock_reentrant():
    """Same agent can re-acquire its own lock."""
    lock = TaskLock()
    ok1, _ = lock.acquire("task-1", "agent-a")
    ok2, reason = lock.acquire("task-1", "agent-a")
    assert ok1 is True
    assert ok2 is True
    assert reason == "already_held"


def test_rate_limiter():
    """Token bucket rate limiting."""
    limiter = RateLimiter(tool_rate_limits={"search": 2.0})
    ok1, _ = limiter.try_acquire("search")
    ok2, _ = limiter.try_acquire("search")
    ok3, reason = limiter.try_acquire("search")

    assert ok1 is True
    assert ok2 is True
    assert ok3 is False
    assert "rate_limited" in reason


def test_rate_limiter_no_limit():
    """Tools without rate limits always pass."""
    limiter = RateLimiter()
    ok, _ = limiter.try_acquire("any_tool")
    assert ok is True


def test_metrics():
    """Metrics tracking."""
    m = GlueMetrics()
    m.record_tool_call(deduped=False, cache_hit=False)
    m.record_tool_call(deduped=True, cache_hit=True)
    m.record_tool_call(deduped=True, cache_hit=True)

    assert m.tool_calls_total == 3
    assert m.tool_calls_deduped == 2
    assert m.dedup_rate == 2 / 3
    assert m.cache_hits == 2

    report = m.report()
    assert "AgentGlue Report" in report


def test_glue_integration():
    """Full integration: AgentGlue decorator with dedup."""
    glue = AgentGlue(rate_limiter=False, shared_memory=False)
    call_count = 0

    @glue.tool()
    def compute(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    r1 = compute(5)
    r2 = compute(5)  # deduped
    r3 = compute(10) # new call

    assert r1 == 10
    assert r2 == 10
    assert r3 == 20
    assert call_count == 2
    assert glue.metrics.tool_calls_deduped == 1


def test_glue_report():
    """Report generation works."""
    glue = AgentGlue()
    report = glue.report()
    assert "AgentGlue Report" in report
    assert "dedup" in report.lower()


if __name__ == "__main__":
    tests = [
        test_dedup_exact_match,
        test_dedup_ttl_expiry,
        test_shared_memory_basic,
        test_shared_memory_private_scope,
        test_shared_memory_confidence,
        test_task_lock_basic,
        test_task_lock_reentrant,
        test_rate_limiter,
        test_rate_limiter_no_limit,
        test_metrics,
        test_glue_integration,
        test_glue_report,
    ]
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print("SMOKE_CHECK_OK")
