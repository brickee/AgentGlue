# AgentGlue — Project Plan

## North Star

Build a **framework-agnostic runtime middleware** for multi-agent systems that eliminates coordination waste (duplicate work, rate limit storms, memory blindness, task conflicts) with zero intrusion into existing agent logic.

## Origin

This project evolved from AgentGym (a DES multi-agent simulator). Key insight: the coordination problems we were simulating (dedup, rate limiting, shared memory, conflict detection) are better solved as a **runtime layer** than a **simulator**. The simulator can't model LLM behavior, but a middleware doesn't need to — it operates on real tool calls in real time.

Reused from AgentGym:
- Resource allocator with token bucket rate limiting and backpressure policies
- Event recording and duplicate detection analytics
- State validation and lifecycle invariant checking
- Metrics computation (per-task normalization, communication cost)
- World state schema (adapted for runtime context)

## Architecture

```
Agent Framework
    |
    v
AgentGlue Runtime
  ├── ToolProxy        — intercepts tool calls, applies dedup + cache
  ├── SharedMemory     — cross-agent knowledge store with TTL + confidence
  ├── RateCoordinator  — shared token buckets, adaptive backpressure
  ├── TaskLock         — intent declaration, conflict detection
  ├── EventBus         — internal event stream for all components
  └── Observer         — metrics collection, reporting, JSONL export
    |
    v
Tools / APIs
```

## Milestones

### M0 — Project Foundation (Day 1)
- [x] Repo scaffolding
- [x] README with vision and API sketch
- [x] PLAN.md / PROGRESS.md / NEXT_TODO.md
- [x] Reuse core modules from AgentGym (allocator, events, validator, metrics, replay)
- [x] pyproject.toml + basic package structure
- [ ] GitHub repo created

### M1 — Tool Call Dedup + Cache (Week 1)
- [ ] ToolProxy class: decorator-based tool wrapping
- [ ] Exact-match dedup (hash tool name + args)
- [ ] TTL-based result cache
- [ ] Semantic dedup via embedding similarity (optional, requires embedding model)
- [ ] Cache invalidation API
- [ ] Metrics: dedup hit rate, cache hit rate, calls saved
- [ ] Tests + smoke check

### M2 — Shared Memory (Week 2)
- [ ] SharedMemory store: key-value with metadata (TTL, confidence, source agent)
- [ ] Auto-publish: tool results optionally broadcast to shared memory
- [ ] Scoping: private / shared / team
- [ ] Staleness detection and confidence decay
- [ ] Metrics: memory hits, misses, stale reads
- [ ] Tests

### M3 — Rate Coordination (Week 3)
- [ ] RateCoordinator: per-tool shared token bucket across agents
- [ ] Backpressure policies: wait, retry-with-backoff, drop
- [ ] Anti-stampede: jittered retry to prevent synchronized retries
- [ ] Rate limit state sharing across agents
- [ ] Metrics: interventions, wait time, dropped calls
- [ ] Tests

### M4 — Task Locks & Conflict Prevention (Week 4)
- [ ] Intent declaration API: agent announces what it's about to do
- [ ] Conflict detection: warn or block if another agent has same intent
- [ ] Optimistic locking for resource writes
- [ ] Dead-intent cleanup (agent crashed without releasing lock)
- [ ] Metrics: conflicts detected, prevented
- [ ] Tests

### M5 — Observability & Integrations (Week 5+)
- [ ] Summary report generator (text + markdown)
- [ ] JSONL event export for post-hoc analysis
- [ ] Real-time metrics (optional Prometheus/StatsD export)
- [ ] CrewAI integration adapter
- [ ] LangGraph integration adapter
- [ ] AutoGen integration adapter
- [ ] Documentation + tutorial

## Non-Goals (for now)
- Not a framework — does not replace AutoGen/CrewAI/LangGraph
- Not an orchestrator — does not decide task assignment
- No LLM calls inside the middleware — deterministic behavior only
- No distributed deployment (single-process first, multi-process later)

## Weekly Operating Rules
1. Each milestone ends with working tests and a smoke check.
2. Every feature must report its own metrics.
3. Keep the API surface minimal — decorator + middleware pattern only.
4. README examples must work as-is (copy-pasteable).
