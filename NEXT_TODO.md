# Next TODO

## Immediate
1. Decide whether to add single-flight / in-flight coalescing for identical tool calls; the new concurrent probe shows current behavior is cache-after-first-call only.
2. Add one tiny example script under `examples/` that prints a real v0.1 report.
3. Decide whether shared-memory auto-publish should remain enabled by default or become opt-in for a cleaner v0.1 story.
4. Record repeated baseline vs AgentGlue v0.1 metrics on at least one medium-sized Python repo.

## Next
5. Expose JSONL export from the recorder in a documented example.
6. Add one second scenario with partial-overlap queries to measure what exact-match dedup misses.
7. Add semantic dedup only if exact-match dedup leaves obvious savings on the table.
8. Tighten shared-memory metrics on the runtime path.
9. Add a minimal integration adapter skeleton (likely CrewAI or LangGraph).
10. Improve rate-limit ergonomics if the benchmark shows real pressure there.
11. Add benchmark regression checks to CI once the harness stabilizes.
