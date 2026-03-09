# AgentGlue — Morning memo (2026-03-09)

## Bottom line

**AgentGlue currently is a thin local runtime wrapper for shared tool calls, with one real and defensible capability: exact-match dedup + TTL caching + basic observability.**

That is enough to be interesting.
It is **not yet** enough to justify the broader story implied by the name unless the project stays disciplined.

My updated view after reading the repo and re-running the first test:
- **More positive** on the narrow v0.1 than I was on the broad concept.
- **More skeptical** of the larger product surface if it expands too early.
- The first benchmark is **good signal but not strong proof**.
- The next 1-2 iterations should be about **turning one good anecdote into a repeatable claim**, not adding more middleware categories.

---

## What AgentGlue currently is

In actual code terms, AgentGlue v0.1 is:
- a decorator-based wrapper around Python tool functions
- a hash-based exact-match cache keyed on `tool_name + args + kwargs`
- TTL invalidation and manual invalidation
- in-memory metrics and event recording
- optional scaffolding for shared memory, rate limiting, and task locks

In practical product terms, it is:

> **“A coordination shim for shared tool use in multi-agent systems, currently proving value on duplicate tool calls.”**

That is the honest positioning.

What it is **not** yet:
- not a framework integration layer in any meaningful sense
- not a production coordination runtime
- not semantic dedup
- not a distributed/shared-state system
- not yet a robust solution for rate coordination or task conflicts

The code reflects that pretty honestly now, which is good. The docs mostly stopped overclaiming.

---

## What seems genuinely promising

### 1. The thin-runtime framing is the right instinct
This is the best part of the project.

Trying to be “the next agent framework” would be a graveyard shift. Trying to sit **below** frameworks and intercept waste at the tool boundary is much more plausible.

That layer is:
- measurable
- composable
- easy to explain
- hard for framework authors to object to

If this works, it could become a small but sharp piece of infrastructure rather than another orchestration cathedral.

### 2. Exact-match dedup is already useful on repo exploration
The first real test is narrow, but it shows the core idea is not imaginary.

Re-run this morning still lands at basically the same result:
- baseline underlying executions: **20**
- AgentGlue underlying executions: **11**
- calls saved: **9**
- dedup rate: **45%**
- wall-clock roughly **191.7 ms -> 101.4 ms** on the scripted sequential run

That is a clean win for the exact kind of workload you picked: overlapping repo search/read/list behavior.

This matters because many multi-agent coding systems really do converge on the same hot files, grep patterns, and directory listings almost immediately. The benchmark is not fake in that sense.

### 3. The observability story is already decent for v0.1
The event stream + metrics + human-readable report are enough to understand what happened without swimming through sludge.

That matters more than it sounds. Middleware without inspectability becomes religion very quickly.

### 4. The codebase is currently small enough to pivot cleanly
This is an advantage right now.

The project has not yet metastasized into adapters, dashboards, policy engines, and an identity crisis. That means you can still choose a crisp product direction.

---

## What seems weak / risky / overclaimed

### 1. The name and roadmap still want to be broader than the evidence
There is a recurring temptation in the repo to bundle four different ideas into one product:
- dedup/cache
- shared memory
- rate coordination
n- task conflict prevention

Those are related, but they are **not the same product**.

Right now only the first one is actually earning its keep.

Risk: AgentGlue becomes a bag of “agent coordination primitives” that sounds important but does not own a single killer use case.

My take: **do not sell the umbrella yet. Sell the knife.**

### 2. Shared memory is the most dangerous overreach area
The shared-memory module exists, but as product it is still mostly a sketch.

Problems:
- unclear semantics of what should be published
- no meaningful consistency or freshness story beyond TTL
- no conflict-resolution story
- no evidence yet that auto-writing tool outputs into memory is actually useful rather than noisy

In fact, the runtime default still enables shared memory (`AgentGlue()` turns it on), while the README tells users to disable it for the tight v0.1 story. That is a small but important mismatch.

That mismatch is exactly how projects drift from “focused” to “technically yes, conceptually blurry.”

### 3. The current dedup is cache, not true in-flight dedup
This is the biggest technical caveat in the v0.1 story.

What the code does today:
- lookup cache
- if miss: execute tool
- store result
- later identical calls hit cache

What it does **not** obviously do:
- coalesce concurrent identical calls that arrive before the first one completes

That distinction matters a lot.

If two agents hit the same expensive tool at the same time, the current implementation can still double-execute before either result is stored. On a sequential scripted workload, this does not show up. In a real multi-agent concurrent system, it absolutely will.

So the real current claim is:

> **post-first-call exact-match reuse**, not guaranteed in-flight duplicate suppression.

That is still useful. But it is less magical than “dedup” sounds.

### 4. The first benchmark is vulnerable to “nice demo, but scripted” criticism
Which, to be fair, is a valid criticism.

The current test uses:
- deterministic agent plans
- sequential execution
- hand-designed overlap
- a local shell-backed repo workload

That is a reasonable first proof-of-value harness.
It is **not** enough to establish general usefulness.

Specifically, it likely overstates wins from:
- perfect exact-match repetition
- warm-cache behavior in a non-concurrent flow
- absence of correctness checks beyond output preservation

So: good first result, not publication-grade evidence.

### 5. The recorder helper bug is a tiny issue with big symbolic importance
`detect_duplicates()` looks only for `tool_call`, while the runtime records saved calls as `tool_call_deduped`.

So the benchmark summary says “9 calls saved,” but the duplicate detector reports zero duplicates.

This is not a runtime failure. But it is a bad smell because it means the **analysis layer and runtime semantics are already drifting apart**.

That is exactly the sort of thing that quietly poisons benchmark credibility later.

---

## Is the first benchmark convincing or misleading?

## Short answer
**Convincing as an existence proof. Misleading if treated as a general benchmark.**

## Why it is convincing
It demonstrates something real:
- the wrapped runtime intercepts repeated calls
- repeated repo exploration behavior does happen
- exact-match reuse can save a meaningful fraction of underlying executions
- the savings are legible in trace form

That is enough to say the project has a live core.

## Why it is misleading if overstated
It is still favorable to AgentGlue in several ways:
- scripted overlap is cleaner than real agent behavior
- sequential execution sidesteps the hardest dedup case (true concurrency)
- exact query/file matches are common here by construction
- no comparison yet across multiple repos or workloads
- no partial-overlap / near-duplicate analysis

So I would phrase the result as:

> **“On a deterministic repo-exploration workload with overlapping tool usage, AgentGlue v0.1 reduced underlying executions by 45%.”**

That statement is fair.

I would **not** yet say:
- “AgentGlue improves multi-agent systems by ~45%”
- “AgentGlue prevents duplicate work in production”
- “The benchmark proves broad value”

That would be brochure behavior.

---

## Product positioning: what this should probably be

My current best strategic read:

### Best near-term positioning
**AgentGlue should be positioned as a tool-call coordination/cache layer for multi-agent coding and retrieval workflows.**

Not “general multi-agent runtime middleware.”
Not yet.

The most believable wedge is something like:
- shared search/read/list/file-access workloads
- coding agents / repo exploration / RAG-ish retrieval tools
- environments where multiple agents redundantly hit the same tools

This wedge is attractive because:
- the waste is common
- the value is measurable
- the integration surface is simple
- you can benchmark it without theological arguments about agent quality

### Less attractive positioning right now
- generalized agent memory substrate
- rate-limit operating system for agent swarms
- conflict-prevention control plane

Those may become future branches, but they are not where you have proof.

If you keep the story too broad too early, people will correctly ask: “Why is this one project instead of four half-built utilities?”

---

## Exact next steps I recommend

## Iteration 1: make the benchmark hard to dismiss
This is the most important next move.

### 1. Fix the duplicate-analysis/event-schema mismatch
Do this first. It is tiny and removes avoidable benchmark embarrassment.

Specifically:
- make recorder helpers understand `tool_call_deduped`
- or define one canonical benchmark-facing event contract and normalize into it

### 2. Turn the current script into a repeatable benchmark harness
Not fancy. Just credible.

Add:
- multiple runs
- stable output format
- per-tool savings table
- median + p90 summary
- explicit benchmark metadata: repo, TTL, agent count, scenario name

You do **not** need a giant framework. A small reproducible harness is enough.

### 3. Run it on at least 2-3 repos of different shapes
Ideal mix:
- one medium Python infra repo
- one app-style repo with broader file spread
- maybe one repo where overlap is naturally lower

This tells you whether the first result was real signal or just an especially cooperative workload.

### 4. Add one concurrent or near-concurrent scenario
This is important because the current design likely misses true in-flight coalescing.

You need to know:
- how much benefit survives under concurrent invocation
- whether “cache-after-first-call” is enough in practice
- whether an in-flight registry/future table is worth implementing

If concurrency exposes a big gap, that is probably the real M1.6 feature.

## Iteration 2: tighten the product, not the feature count
Once the harness exists, use it to decide the next engineering move.

### 5. Decide whether in-flight dedup belongs in the core v0.1.x path
My guess: yes, probably.

Reason: if you want to claim “dedup for multi-agent systems,” coalescing simultaneous identical calls is much more central than shared memory is.

A likely better next feature than semantic dedup is:
- **single-flight / in-flight call coalescing** for identical requests

That would materially strengthen the core story.

### 6. Make shared memory opt-in by default unless you can prove it helps
Right now the clean story is dedup/cache/observability.

So the default constructor should probably align with that story, or at least docs should stop pretending the default matches the recommended posture.

If shared memory stays default-on while being non-core, people will infer it is part of the main value proposition. That is premature.

### 7. Add one tiny real example under `examples/`
A dead-simple example that:
- wraps 2-3 tools
- shows repeated calls across agents
- prints metrics/report
- optionally dumps JSONL

This helps more than another abstract roadmap paragraph.

---

## What I would *not* do next

I would **not** do these yet:
- semantic dedup
- framework-specific integration adapters beyond a stub
- richer dashboards/traces
- stronger shared-memory product claims
- rate coordination expansion unless a benchmark demands it

All of those are tempting. All of them risk turning a focused project into an adjective generator.

The project does not need more surface area right now.
It needs **stronger evidence on the narrow claim**.

---

## Technical observations from the code

A few concrete notes from reading the implementation:

### Runtime defaults are not fully aligned with the stated v0.1 story
`AgentGlue()` currently defaults to:
- dedup: on
- shared_memory: on
- task_lock: on
- rate_limiter: off

But the docs repeatedly say the usable v0.1 path is dedup + cache + observability, with the others scaffolded.

That is not catastrophic, but it is conceptually sloppy.

### Shared memory currently writes tool outputs but is not meaningfully used in the wrapped path
So it adds conceptual weight without demonstrated value.

### Metrics are readable enough
That part is solid. The report exposes the right first-order numbers.

### Tests are fine for smoke coverage, but they do not yet defend the strategic claims
The tests verify local mechanics.
They do not validate:
- concurrency behavior
- benchmark correctness invariants
- stale-result risks on mutable resources
- true integration expectations under agent frameworks

That is normal at this stage, just worth stating plainly.

---

## New strategic view compared with earlier today

Here is the real update in my thinking:

### I am **more bullish** on AgentGlue as a narrow wedge
Before reading the implementation and result closely, the project could have been pure middleware perfume.

It is not.
There is a real, clean wedge here:
- shared tool-use dedup
- especially for coding/repo exploration/retrieval-style multi-agent workloads

That could absolutely be a useful OSS primitive.

### I am **less bullish** on the broad umbrella story
The codebase already hints at the classic trap: grouping several adjacent coordination problems into one concept before one of them has won.

The path to something real is probably:
1. dominate the duplicate-tool-call niche first
2. maybe add in-flight coalescing
3. maybe later broaden into a larger coordination runtime

Not the reverse.

### My sharpest recommendation
If you want this project to matter, make it the **best small thing** before it becomes the **vaguest big thing**.

That is the fork in the road.

---

## Suggested one-sentence positioning right now

If you want a crisp line for README / talking / repo description, I’d use something close to:

> **AgentGlue is a thin runtime layer that reduces redundant shared-tool executions across multiple agents, starting with exact-match dedup, TTL caching, and built-in observability.**

That is accurate, useful, and not trying to cosplay as an operating system.

---

## Final recommendation

**Proceed — but stay narrow.**

The project has enough real signal to keep going.
The next milestone is not “more features.”
It is:
- better benchmark rigor
- clearer product boundaries
- probably in-flight identical-call coalescing if concurrency proves important

If the next round of benchmarks still shows strong savings across a few repos and under some concurrency, AgentGlue starts looking like a legitimately sharp infrastructure primitive.

If not, better to learn that now than after building semantic-memory-themed stained glass around it.
