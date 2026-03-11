# Next TODO

## Immediate
1. ~~Single-flight / in-flight coalescing~~ — **Done.** Concurrent identical calls now share the leader's result via `_InFlight` + `threading.Event`. Metrics track `tool_calls_coalesced`; events include `tool_call_coalesced`.
2. ~~Add one tiny example script under `examples/` that prints a real v0.1 report.~~
3. ~~Decide whether shared-memory auto-publish should remain enabled by default or become opt-in for a cleaner v0.1 story.~~ — **Done.** `AgentGlue()` now defaults to the narrow standalone path with `shared_memory=False` and `task_lock=False`.
4. ~~Record repeated baseline vs AgentGlue v0.1 metrics on at least one medium-sized Python repo.~~

## Next
5. ~~Tighten shared-memory metrics on the runtime path so optional reads/writes are measurable without inflating the default product claim.~~ — **Done.** `SharedMemory` now has honest metrics: writes, reads, hits, misses, stale_reads, private_access_denied, hit_rate. Docs clearly state it's optional/scaffolded.
6. ~~Archive old AgentGym-era benchmark artifacts~~ — **Done.** Moved all AgentGym-targeted benchmark runs to `artifacts/_archived_agentgym_era/` and `artifacts/benchmarks/_archived_agentgym_era/` with README explaining they're historical only. Current canonical benchmark is `standalone_default_smoke/`.
7. Add semantic dedup only if exact-match dedup leaves obvious savings on the table.
8. ~~Add a minimal integration adapter skeleton (likely CrewAI or LangGraph).~~ — **Done via documentation.** Added "Framework Integration" section to README showing CrewAI/LangGraph/AutoGen patterns. The decorator API is already framework-agnostic, so no special adapter code is needed.
9. Improve rate-limit ergonomics if the benchmark shows real pressure there.
10. ~~Decide whether the lightweight benchmark sanity check should stay local-only or become a small CI guard once artifact stability feels boring.~~ — **Done.** The benchmark harness now supports `--target-repo`, smoke coverage runs it against `tests/benchmark_fixture`, and a tiny GitHub Actions workflow covers pytest + executable examples.
