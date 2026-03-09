# AgentGlue

> The missing middleware for multi-agent systems. Drop in between your agents and tools — get dedup, shared memory, rate limiting, conflict prevention, and observability for free.

## The Problem

Multi-agent frameworks (AutoGen, CrewAI, LangGraph) focus on **orchestration** — how agents talk to each other and divide work. But they leave a critical gap: **what happens when multiple agents hit the same tools, fight over the same resources, and do the same work twice?**

In production multi-agent systems, you will see:

- **Duplicate work** — Agent A searches for "transformer papers", Agent B searches for "transformer architecture papers" 30 seconds later. Same intent, wasted API call.
- **Rate limit storms** — 5 agents all hammering the same API, nobody coordinating, everyone getting 429s and retrying at the same time.
- **Memory blindness** — Agent A discovers a crucial fact, Agent B has no idea and wastes 3 tool calls rediscovering it.
- **Task conflicts** — Two agents both start writing to the same file, or both claim the same task.
- **Invisible waste** — No easy way to know how much money and time you're losing to coordination failures.

## The Solution

AgentGlue is a **thin runtime layer** that sits between your agent framework and your tools/APIs:

```
Agent Framework (AutoGen / CrewAI / LangGraph / custom)
    |
[AgentGlue] <-- dedup, shared memory, rate coordination, task locks, observability
    |
Tools / APIs
```

It is **not** a framework. It does not replace your orchestrator. It makes your existing multi-agent system smarter about shared resources.

## Quickstart

```python
from agentglue import AgentGlue

glue = AgentGlue()

# Wrap your tools — that's it
@glue.tool()
def search(query: str) -> str:
    return call_search_api(query)

# Or wrap at framework level
from agentglue.integrations import CrewAIMiddleware
crew = Crew(agents=[...], middleware=[CrewAIMiddleware(glue)])
```

After your agents run, get a report:

```
AgentGlue Report:
  Tool calls saved by dedup:  47/120 (39%)
  Rate limit interventions:   12
  Task conflicts prevented:   3
  Shared memory hits:         28
  Estimated cost saved:       ~$2.40
```

## Features

### v0.1 — Tool Call Dedup + Cache
- Exact-match and semantic dedup for tool calls across agents
- Configurable TTL cache with invalidation
- Zero-config: just wrap your tools

### v0.2 — Shared Memory
- Agent A's discoveries are automatically visible to Agent B
- TTL, confidence scores, and staleness tracking
- Private vs shared vs team-scoped memory

### v0.3 — Rate Coordination
- Cross-agent rate limit awareness (shared token bucket)
- Adaptive backpressure: wait / retry-with-backoff / drop
- No more synchronized retry storms

### v0.4 — Task Locks & Conflict Prevention
- Distributed intent declaration ("I'm working on task X")
- Conflict detection before work starts
- Optimistic locking for file/resource writes

### v0.5 — Observability
- Real-time coordination metrics dashboard
- Redundancy score, coordination overhead ratio, scaling efficiency
- JSONL event log for post-hoc analysis

## Design Principles

1. **Zero intrusion** — Works as a decorator or middleware. No changes to your agent logic.
2. **Framework agnostic** — Works with any Python-based agent system.
3. **Incremental adoption** — Enable one feature at a time. Each is independently useful.
4. **Observable by default** — Every intervention is logged and measurable.
5. **No magic** — Deterministic behavior, no hidden LLM calls, no surprise costs.

## Project Status

Early development. Core dedup and shared memory modules under construction.

## License

MIT
