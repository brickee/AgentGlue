# Next TODO

## Immediate
1. Fix duplicate-trace analysis so recorder helpers understand AgentGlue runtime dedup events (currently `tool_call_deduped`).
2. Turn the first repo-exploration script into a tiny repeatable benchmark harness (multiple runs + per-tool summaries).
3. Add one tiny example script under `examples/` that prints a real v0.1 report.
4. Decide whether shared-memory auto-publish should remain enabled by default or become opt-in for a cleaner v0.1 story.

## Next
5. Record repeated baseline vs AgentGlue v0.1 metrics on at least one medium-sized Python repo.
6. Expose JSONL export from the recorder in a documented example.
7. Add one second scenario with partial-overlap queries to measure what exact-match dedup misses.
8. Add semantic dedup only if exact-match dedup leaves obvious savings on the table.
9. Tighten shared-memory metrics on the runtime path.
10. Add a minimal integration adapter skeleton (likely CrewAI or LangGraph).
11. Improve rate-limit ergonomics if the benchmark shows real pressure there.
12. Add benchmark regression checks to CI once the harness stabilizes.
