# AgentGlue

> Thin runtime layer for shared tool-call coordination in multi-agent systems — exact-match dedup, TTL cache, single-flight, and baseline observability.

## The problem

Multi-agent frameworks (AutoGen, CrewAI, LangGraph) are good at orchestration — who does what, in what order. Production waste often happens one layer lower: when multiple agents touch the same tools, APIs, files, and shared state without coordination.

That creates a predictable set of problems:
- **Duplicate work** — multiple agents make the same tool calls.
- **Rate limit storms** — agents independently hammer the same external service.
- **Memory blindness** — one agent learns something useful, others rediscover it expensively.
- **Task conflicts** — agents collide on the same file, task, or shared resource.
- **Observability gaps** — you cannot tell where the waste is coming from.

## What it does

- **Exact-match tool-call dedup** — same tool + same args = one execution
- **In-flight coalescing (single-flight)** — concurrent identical calls share one execution
- **TTL result cache** — sequential repeat calls served from cache
- **Cross-process SQLite cache (v0.3)** — multiple agents/processes share a single cache via sidecar
- **Cache invalidation API**
- **Baseline metrics + event recording**
- **Simple decorator API**

What this means in plain English:
- if two agents make the **same call at the same time**, single-flight lets one lead and the others wait
- if another agent makes the **same call shortly after**, the TTL cache serves it
- in v0.3, agents in **different processes** also share the cache (via SQLite sidecar)
- if the calls are only *similar* rather than identical, AgentGlue does **not** merge them

## Architecture

```text
Agent Framework (AutoGen / CrewAI / LangGraph / custom)
    |
[AgentGlue] <-- dedup, cache, baseline observability
    |
Tools / APIs
```

## Quickstart

```python
from agentglue import AgentGlue

# Keep v0.1 tight: dedup + cache + observability
# Disable the other middleware unless you are actively experimenting.
glue = AgentGlue(shared_memory=False, rate_limiter=False, task_lock=False)

@glue.tool(ttl=300)
def search_code(query: str) -> str:
    print(f"real search for: {query}")
    return f"results for {query}"

print(search_code("rate limiter", agent_id="agent-a"))
print(search_code("rate limiter", agent_id="agent-b"))  # dedup hit
print(search_code("cache invalidation", agent_id="agent-c"))

print(glue.report())
```

Example output:

```text
real search for: rate limiter
real search for: cache invalidation
AgentGlue Report:
  Observed tool calls:      3
  Underlying executions:    2
  Calls saved by dedup:     1/3 (33%)
  Cache hit rate:           33%
  Avg observed latency:     0.01 ms
  Avg underlying latency:   0.01 ms
  Rate limit interventions: 0
  Shared memory writes:     0
  Shared memory hits:       0
  Task conflicts prevented: 0
```

## Benchmark: No-Glue vs With-Glue

Measured on the sidecar integration test suite (100 tests). "No-Glue" = every agent executes the real tool every time. "With-Glue" = first agent executes, later agents get SQLite cache hits.

| Scenario | Agents | Calls | No-Glue | With-Glue | Saved | Speedup | Hit Rate |
|---|:---:|:---:|---:|---:|---:|:---:|:---:|
| 2-agent same read | 2 | 2 | 11.3ms | 5.6ms | +5.7ms | 2.0x | 50% |
| 3-agent same search | 3 | 3 | 53.4ms | 7.9ms | +45.5ms | **6.8x** | 67% |
| 3-agent mixed overlap | 3 | 7 | 62.3ms | 18.8ms | +43.5ms | 3.3x | 57% |
| 4-agent code review | 4 | 12 | 69.7ms | 22.8ms | +46.9ms | 3.1x | 75% |
| 5-agent feature branches | 5 | 15 | 134.5ms | 37.7ms | +96.7ms | 3.6x | 60% |
| 8-agent full scan | 8 | 40 | 187.1ms | 54.8ms | +132.3ms | 3.4x | **88%** |
| 10-agent heavy overlap | 10 | 40 | 329.8ms | 65.6ms | +264.2ms | **5.0x** | 85% |
| 4-agent disjoint (no overlap) | 4 | 4 | 18.2ms | 21.7ms | -3.4ms | 0.8x | 0% |
| **Total** | | **123** | **866.4ms** | **234.9ms** | **+631.5ms** | **3.7x** | **76%** |

Key takeaways:
- **73% total time saved** across 123 tool calls (866ms → 235ms)
- More agents + more overlap = bigger wins (10-agent scenario: **5.0x**)
- Search operations benefit most (grep is expensive): **6.8x** speedup
- Cache check latency: **0.6ms median** (p95: 0.75ms)
- Zero overhead when there's no overlap (disjoint scenario: -3.4ms from cache-check HTTP cost)

Run the benchmark yourself:

```bash
PYTHONPATH=src python3 -m pytest tests/test_sidecar_benchmark.py -v -s
# or standalone:
PYTHONPATH=src python3 tests/test_sidecar_benchmark.py
```

## Integrations

### OpenClaw Plugin (v0.3)

AgentGlue is available as a self-contained npm package for OpenClaw:

```bash
openclaw plugins install openclaw-agentglue
# or
npm install openclaw-agentglue
```

**Features:**
- SQLite-backed cross-process cache — all sub-agents share one cache
- Auto-managed Python sidecar with health monitoring and restart handling
- `after_tool_call` hook auto-caches all read-only tool results
- 3 cache-aware repo exploration tools (`agentglue_cached_read`, `agentglue_cached_search`, `agentglue_cached_list`)
- Metrics and health endpoints
- No separate AgentGlue install needed — Python library bundled in the package

See [`openclaw-agentglue/README.md`](./openclaw-agentglue/README.md) for full documentation.

## API

### Wrap a tool

```python
from agentglue import AgentGlue

glue = AgentGlue(shared_memory=False, rate_limiter=False, task_lock=False)

@glue.tool(ttl=60)
def fetch_doc(path: str) -> str:
    return open(path).read()
```

### Invalidate a single cached result

```python
glue.invalidate("fetch_doc", "README.md")
```

### Clear the cache

```python
glue.clear_cache()
```

### Access summary metrics programmatically

```python
summary = glue.summary()
print(summary["calls_saved"])
print(summary["cache_hit_rate"])
```

### Export runtime events to JSONL

```python
exported = glue.export_events_jsonl("artifacts/examples/my_run.events.jsonl")
print(exported["event_count"])
print(exported["duplicate_analysis"]["by_tool"])
```

If you want to re-open an exported log later without a live `AgentGlue` instance:

```python
from agentglue.core.recorder import summarize_jsonl

summary = summarize_jsonl("artifacts/examples/my_run.events.jsonl")
print(summary["duplicate_analysis"]["total_duplicates"])
```

## Framework Integration

AgentGlue is framework-agnostic. The `@glue.tool()` decorator wraps any Python function, so it works with any agent framework that calls Python callables.

**CrewAI:**

```python
from crewai_tools import tool
from agentglue import AgentGlue

glue = AgentGlue()

@glue.tool(ttl=60)
@tool("Search codebase")
def search_code(query: str) -> str:
    """Search the codebase for relevant code."""
    return run_search(query)
```

**LangGraph:**

```python
from langchain_core.tools import tool
from agentglue import AgentGlue

glue = AgentGlue()

@glue.tool(ttl=60)
@tool
def read_file(path: str) -> str:
    """Read a file from the codebase."""
    return open(path).read()
```

**AutoGen:**

```python
from agentglue import AgentGlue

glue = AgentGlue()

@glue.tool(ttl=60)
def list_files(directory: str) -> list:
    """List files in a directory."""
    return os.listdir(directory)

# Register with AutoGen agent
# agent.register_for_execution()(list_files)
```

The pattern is the same: wrap your tool function with `@glue.tool()`, then register it with your framework as usual. AgentGlue intercepts calls, deduplicates, caches, and records metrics — transparently to the framework.

## Metrics

AgentGlue tracks:
- observed tool calls / underlying executions / calls saved
- coalesced calls (single-flight)
- dedup rate / cache hit rate
- average observed vs underlying latency
- rate-limit interventions / shared-memory writes / task conflicts

## Current status

**v0.3** — production-ready for multi-agent tool coordination:

- exact-match dedup keyed by tool name + args/kwargs hash
- in-flight coalescing (single-flight): concurrent identical calls wait for the leader's result
- TTL cache with per-tool configuration
- **SQLite backend for cross-process cache sharing** (v0.3)
- **OpenClaw plugin with auto-managed sidecar** (v0.3)
- cache invalidation and full-cache clearing
- text report + dict summary
- event recording for tool calls, dedup hits, coalesced waits, and completions
- 100-test integration benchmark suite with baseline comparison

What remains intentionally deferred:
- semantic dedup (similar but non-identical calls)
- production-grade shared memory
- cross-agent rate coordination policy layer

## Design principles

1. **Thin runtime, not a framework**
2. **Framework agnostic**
3. **Observable by default**
4. **Incremental adoption**
5. **No hidden LLM calls inside middleware**

## Development

```bash
# Run examples
PYTHONPATH=src python3 examples/basic_report.py
PYTHONPATH=src python3 examples/recorder_export.py

# Run all tests (unit + smoke + sidecar benchmark)
PYTHONPATH=src pytest -q

# Run sidecar benchmark only (100 tests, includes baseline comparison)
PYTHONPATH=src python3 -m pytest tests/test_sidecar_benchmark.py -v -s

# Run standalone benchmark with report
PYTHONPATH=src python3 tests/test_sidecar_benchmark.py

# Run repo exploration benchmark
PYTHONPATH=src python3 scripts/benchmark_repo_exploration.py --runs 3 --label local_run
```

## Disclaimer

This project is a personal open-source project developed in my personal capacity. It is not affiliated with, endorsed by, or representing any employer or organization I am associated with. All work on this project is performed on personal time and with personal resources.

## License

MIT
