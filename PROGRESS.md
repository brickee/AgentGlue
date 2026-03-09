# Progress Log

## 2026-03-09 (Day 0 — Project Init)
- Created project from AgentGym pivot.
- Defined vision: framework-agnostic multi-agent runtime middleware.
- Wrote README with motivation, API sketches, and feature roadmap.
- Created PLAN.md with architecture and milestones (M0-M5).
- Ported reusable modules from AgentGym:
  - `core/events.py` — event schema (adapted: real timestamps replace sim_time)
  - `core/allocator.py` — resource allocator with token bucket + backpressure
  - `core/validator.py` — state machine lifecycle validation
  - `core/recorder.py` — JSONL event recording + duplicate detection (from replay.py)
  - `core/metrics.py` — per-task metric normalization (from eval/metrics.py)
  - `core/state.py` — runtime state schema (from world.py, adapted)
- Scaffolded middleware layer: `ToolProxy`, `SharedMemory`, `RateCoordinator`, `TaskLock`.
- Set up pyproject.toml and package structure.

### Decisions
- Single-process first. No distributed coordination until proven needed.
- Decorator + middleware pattern only. No framework lock-in.
- Every component independently useful. Users enable what they need.
