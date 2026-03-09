# AgentGlue Benchmark Summary

- label: `2026-03-09_dedup_observability`
- target_repo: `/home/ubuntu/.openclaw/workspace/projects/AgentGym`
- scenario: `repo_exploration`
- runs: **3**
- dedup_ttl_s: **600.0**

## Repo exploration aggregate

- baseline underlying executions mean: **20**
- agentglue underlying executions mean: **11**
- agentglue calls saved mean: **9**
- agentglue dedup rate mean: **0.45**
- baseline wall clock mean: **177.985333 ms**
- agentglue wall clock mean: **98.555333 ms**

## Per-tool mean summary

- `list_files`: observed=4, underlying=2, saves=2, dedup_rate=0.5
- `read_file`: observed=8, underlying=4, saves=4, dedup_rate=0.5
- `search_code`: observed=8, underlying=5, saves=3, dedup_rate=0.375

## Concurrent probe

- underlying_call_count: **2**
- deduped_calls_in_metrics: **1**
- finding: Concurrent identical calls both executed underlying work; only the later post-flight call was deduped. This shows cache-after-first-call behavior, not in-flight single-flight coalescing.

## Recommendation

Implement in-flight coalescing only if you want AgentGlue to claim shared-tool dedup under true concurrent pressure. The current evidence says the v0.1 path is exact-match TTL cache + post-first-call dedup, which is useful but narrower.
