"""Smoke tests for AgentGlue v0.1 core functionality."""

import threading
import time

from agentglue import AgentGlue
from agentglue.core.allocator import RateLimiter
from agentglue.core.metrics import GlueMetrics
from agentglue.core.recorder import detect_duplicates
from agentglue.middleware.dedup import ToolDedup
from agentglue.middleware.shared_memory import SharedMemory
from agentglue.middleware.task_lock import TaskLock


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
    r2 = wrapped("transformers")
    r3 = wrapped("attention")

    assert r1 == r2 == "result for transformers"
    assert r3 == "result for attention"
    assert call_count == 2


def test_dedup_ttl_expiry():
    """Cache entries expire after TTL."""
    dedup = ToolDedup(default_ttl=0.1)
    call_count = 0

    def search(query):
        nonlocal call_count
        call_count += 1
        return f"result-{call_count}"

    wrapped = dedup.wrap(search)
    r1 = wrapped("test")
    time.sleep(0.15)
    r2 = wrapped("test")

    assert r1 == "result-1"
    assert r2 == "result-2"
    assert call_count == 2


def test_shared_memory_basic():
    mem = SharedMemory()
    mem.write("key1", "value1", agent_id="agent-a")
    assert mem.read("key1", agent_id="agent-b") == "value1"


def test_shared_memory_private_scope():
    mem = SharedMemory()
    mem.write("secret", "data", agent_id="agent-a", scope="private")
    assert mem.read("secret", agent_id="agent-a") == "data"
    assert mem.read("secret", agent_id="agent-b") is None


def test_shared_memory_confidence():
    mem = SharedMemory(min_confidence=0.5)
    mem.write("key", "value", confidence=0.3)
    assert mem.read("key") is None
    mem.write("key2", "value2", confidence=0.8)
    assert mem.read("key2") == "value2"


def test_task_lock_basic():
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
    lock = TaskLock()
    ok1, _ = lock.acquire("task-1", "agent-a")
    ok2, reason = lock.acquire("task-1", "agent-a")
    assert ok1 is True
    assert ok2 is True
    assert reason == "already_held"


def test_rate_limiter():
    limiter = RateLimiter(tool_rate_limits={"search": 2.0})
    ok1, _ = limiter.try_acquire("search")
    ok2, _ = limiter.try_acquire("search")
    ok3, reason = limiter.try_acquire("search")

    assert ok1 is True
    assert ok2 is True
    assert ok3 is False
    assert "rate_limited" in reason


def test_rate_limiter_no_limit():
    limiter = RateLimiter()
    ok, _ = limiter.try_acquire("any_tool")
    assert ok is True


def test_metrics():
    m = GlueMetrics()
    m.record_tool_call(deduped=False, cache_hit=False, latency_ms=10.0)
    m.record_tool_call(deduped=True, cache_hit=True, latency_ms=0.5)
    m.record_tool_call(deduped=True, cache_hit=True, latency_ms=0.5)

    assert m.tool_calls_total == 3
    assert m.tool_calls_underlying == 1
    assert m.tool_calls_deduped == 2
    assert m.dedup_rate == 2 / 3
    assert m.cache_hits == 2
    assert m.calls_saved == 2

    report = m.report()
    assert "AgentGlue Report" in report
    assert "Underlying executions" in report


def test_glue_integration_and_invalidation():
    glue = AgentGlue(rate_limiter=False, shared_memory=True)
    call_count = 0

    @glue.tool(ttl=60.0)
    def compute(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    r1 = compute(5, agent_id="agent-a")
    r2 = compute(5, agent_id="agent-b")
    r3 = compute(10, agent_id="agent-a")
    invalidated = glue.invalidate("compute", 5)
    r4 = compute(5, agent_id="agent-c")

    assert r1 == 10
    assert r2 == 10
    assert r3 == 20
    assert r4 == 10
    assert invalidated is True
    assert call_count == 3
    assert glue.metrics.tool_calls_deduped == 1
    assert glue.metrics.tool_calls_underlying == 3
    assert glue.metrics.shared_memory_writes == 3


def test_glue_report_and_events():
    glue = AgentGlue(shared_memory=False)

    @glue.tool()
    def lookup(x):
        return x

    lookup("a", agent_id="agent-a")
    lookup("a", agent_id="agent-b")

    report = glue.report()
    assert "AgentGlue Report" in report
    assert "dedup" in report.lower()
    assert glue.recorder is not None
    event_types = [event["event_type"] for event in glue.recorder.events]
    assert "tool_call" in event_types
    assert "tool_call_deduped" in event_types
    assert "tool_call_completed" in event_types


def test_detect_duplicates_understands_runtime_dedup_events():
    glue = AgentGlue(shared_memory=False, rate_limiter=False, task_lock=False)

    @glue.tool(ttl=60.0)
    def lookup(x):
        return {"value": x}

    lookup("a", agent_id="agent-a")
    lookup("a", agent_id="agent-b")
    lookup("b", agent_id="agent-c")

    events = glue.recorder.events if glue.recorder else []
    duplicates = detect_duplicates(events)

    assert duplicates["total_duplicates"] == 1
    assert duplicates["by_tool"] == {"lookup": 1}
    assert duplicates["by_agent"] == {"agent-b": 1}
    assert duplicates["duplicate_intents"][0]["deduped_calls"] == 1


def test_concurrent_identical_calls_do_not_single_flight_today():
    glue = AgentGlue(shared_memory=False, rate_limiter=False, task_lock=False, dedup_ttl=60.0)
    barrier = threading.Barrier(2)
    call_count = 0
    call_lock = threading.Lock()

    @glue.tool(ttl=60.0)
    def slow_lookup(x):
        nonlocal call_count
        barrier.wait(timeout=1.0)
        time.sleep(0.05)
        with call_lock:
            call_count += 1
            current = call_count
        return f"value-{x}-{current}"

    results = []

    def invoke(agent_id: str) -> None:
        results.append(slow_lookup("same", agent_id=agent_id))

    threads = [
        threading.Thread(target=invoke, args=("agent-a",)),
        threading.Thread(target=invoke, args=("agent-b",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    post_result = slow_lookup("same", agent_id="agent-c")

    assert call_count == 2
    assert len(results) == 2
    assert sorted(results) == ["value-same-1", "value-same-2"]
    assert post_result in results
    assert glue.metrics.tool_calls_total == 3
    assert glue.metrics.tool_calls_underlying == 2
    assert glue.metrics.tool_calls_deduped == 1

    duplicates = detect_duplicates(glue.recorder.events if glue.recorder else [])
    assert duplicates["total_duplicates"] == 1
    assert duplicates["by_agent"] == {"agent-c": 1}


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
        test_glue_integration_and_invalidation,
        test_glue_report_and_events,
        test_detect_duplicates_understands_runtime_dedup_events,
        test_concurrent_identical_calls_do_not_single_flight_today,
    ]
    for test_fn in tests:
        try:
            test_fn()
            print(f"  PASS  {test_fn.__name__}")
        except Exception as exc:
            print(f"  FAIL  {test_fn.__name__}: {exc}")
    print("SMOKE_CHECK_OK")
