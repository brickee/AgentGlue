# Progress Log

## 2026-03-09 — v0.1 first usable pass
- Tightened the product story around the real v0.1 surface: exact-match dedup + TTL cache + baseline observability.
- Updated `AgentGlue` runtime to expose:
  - decorator-wrapped tools
  - single-entry cache invalidation
  - full cache clearing
  - event payloads with call hashes and completion latency
- Improved metrics to report:
  - observed tool calls
  - underlying executions
  - calls saved
  - dedup rate
  - cache hit rate
  - basic latency averages
- Kept shared memory, rate limiting, and task lock as scaffolded modules rather than overclaiming them as v0.1-complete features.
- Added `tests/conftest.py` so the test suite works from a source checkout without installing the package first.
- Expanded smoke tests to cover:
  - dedup hit path
  - TTL expiry
  - invalidation
  - event recording
  - updated metrics/report output
- Added `BENCHMARK_PLAN.md` with a concrete evaluation plan and a strong recommendation to start with multi-agent repo search / codebase exploration.
- Updated README / PLAN / NEXT_TODO to match the new status.

## 2026-03-09 — first real repo-exploration test
- Added `scripts/repo_exploration_first_test.py`, a deterministic multi-agent-style repo exploration workload using real shell-backed tools:
  - `list_files`
  - `search_code`
  - `read_file`
- Ran the workload against the local `AgentGym` repo and saved artifacts under `artifacts/first_test_2026-03-09/`.
- Wrote `TEST_RESULT_2026-03-09.md` with the first concrete result.

### First result
- Baseline: **20 observed / 20 underlying**
- AgentGlue: **20 observed / 11 underlying**
- Calls saved: **9**
- Dedup rate: **45%**
- Cache hit rate: **45%**
- Wall-clock on this scripted run dropped from **191.7 ms** to **101.1 ms**

### What changed in my understanding
- Exact-match dedup is already meaningfully useful on repo exploration; this is enough signal to justify building the lightweight benchmark harness next.
- The main immediate follow-up is not “does this work at all?” anymore.
- The main immediate follow-up is:
  1. fix duplicate-trace analysis for runtime dedup events (`tool_call_deduped`)
  2. repeat the benchmark cleanly across runs / repos

### Current status
- The first usable v0.1 path is present and now has one credible real workload result, not just a plan.
- Main working story: wrap repo-exploration tools, save repeated calls, inspect metrics, and inspect JSONL traces.
- Benchmark harness is still lightweight / ad hoc, but the benchmark direction now has concrete evidence behind it.
