# Proposal: Add `result` short-circuit to `before_tool_call` hook

**Date:** 2026-03-23
**Author:** AgentGlue maintainers
**Status:** Draft
**Target:** OpenClaw SDK `before_tool_call` hook enhancement

---

## Problem Statement

The OpenClaw plugin SDK already supports the `before_tool_call` hook (shipped in
v2025.6, refined through #15012, #15635, #16852, #32360). Today the hook result
type allows two actions:

1. **Modify params** — return `{ params: { ... } }` to merge/replace parameters
   before execution.
2. **Block** — return `{ block: true, blockReason: "..." }` to reject the call
   with an error.

There is no way for a handler to **return a result directly** — i.e., short-circuit
the tool execution and supply a cached/synthetic value without the tool actually
running. This is the single missing capability that prevents AgentGlue (and any
caching/memoization plugin) from transparently intercepting _all_ tool calls.

### Current AgentGlue workaround

AgentGlue works around this limitation with a two-pronged approach:

1. **`after_tool_call` hook** — passively caches every tool result after execution.
2. **Proxy tools** (`agentglue_cached_read`, `agentglue_cached_search`,
   `agentglue_cached_list`) — separate tools that check the cache first and fall
   back to sidecar or Node.js execution.

This workaround has significant drawbacks:

- The LLM must learn to prefer `agentglue_cached_*` tools over built-in `read`,
  `grep`, `glob` — requiring system prompt injection and tool denial rules.
- Built-in tools cannot be transparently cached; they must be individually
  wrapped or denied.
- Adding cache coverage for a new tool requires registering another proxy tool.
- The proxy tools duplicate parameter schemas and require ongoing maintenance as
  OpenClaw's built-in tools evolve.

### What `result` short-circuiting enables

With a `result` field in `PluginHookBeforeToolCallResult`, AgentGlue would:

- Intercept **every** tool call via a single `before_tool_call` handler
- Return cached results transparently — the agent sees the same output it would
  get from the real tool
- Eliminate all proxy tools, system prompt injection, and tool denial
  configuration
- Become a zero-config caching layer

---

## Current SDK Types (for reference)

From `dist/plugin-sdk/plugins/types.d.ts` in OpenClaw 2026.3:

```typescript
export type PluginHookBeforeToolCallEvent = {
    toolName: string;
    params: Record<string, unknown>;
    runId?: string;
    toolCallId?: string;
};

export type PluginHookBeforeToolCallResult = {
    params?: Record<string, unknown>;
    block?: boolean;
    blockReason?: string;
};

export type PluginHookToolContext = {
    agentId?: string;
    sessionKey?: string;
    sessionId?: string;
    runId?: string;
    toolName: string;
    toolCallId?: string;
};
```

---

## Proposed API Change

Add a `result` field to `PluginHookBeforeToolCallResult`:

```typescript
export type PluginHookBeforeToolCallResult = {
    // Existing fields (unchanged)
    params?: Record<string, unknown>;
    block?: boolean;
    blockReason?: string;

    // NEW: short-circuit the tool call with this result
    result?: string;
};
```

### Return value semantics

| Return value | Behavior |
|---|---|
| `undefined` / `void` | Proceed with normal execution (no change) |
| `{ params: {...} }` | Merge/replace params, then execute (existing) |
| `{ block: true, blockReason: "..." }` | Block with error (existing) |
| `{ result: "..." }` | **NEW:** Skip execution, use this as the tool result |

When `result` is set, it takes precedence: the tool's `execute()` is never
called, and the string is returned as if the tool had produced it.

If both `result` and `block` are set, `block` takes precedence (fail-safe).

If both `result` and `params` are set, `result` takes precedence (params
modification is meaningless when execution is skipped).

### Priority and multiple handlers

The existing `runModifyingHook` dispatch runs `before_tool_call` handlers
**sequentially** (not parallel), ordered by `priority`. The accumulator merges
results:

```javascript
// Existing accumulator in hook-runner.js:
(acc, next) => ({
    params: next.params ?? acc?.params,
    block: next.block ?? acc?.block,
    blockReason: next.blockReason ?? acc?.blockReason,
})
```

The proposed change extends the accumulator:

```javascript
(acc, next) => ({
    params: next.params ?? acc?.params,
    block: next.block ?? acc?.block,
    blockReason: next.blockReason ?? acc?.blockReason,
    result: next.result ?? acc?.result,    // NEW
})
```

Once any handler in the chain returns `{ result }`, subsequent handlers still
run (they may also set `block`), but the first non-undefined `result` wins
unless a later handler overrides it. This matches the existing semantics for
`params` and `block`.

---

## Implementation Changes Required

### 1. Type definition (`types.d.ts`)

Add `result?: string` to `PluginHookBeforeToolCallResult` (shown above).

### 2. Hook accumulator (hook-runner)

In the `runBeforeToolCall` function (replicated in multiple bundle files):

```javascript
// File: dist/reply-Bm8VrLQh.js (and equivalents)
// Line ~36486
async function runBeforeToolCall(event, ctx) {
    return runModifyingHook("before_tool_call", event, ctx, (acc, next) => ({
        params: next.params ?? acc?.params,
        block: next.block ?? acc?.block,
        blockReason: next.blockReason ?? acc?.blockReason,
        result: next.result ?? acc?.result,    // ADD THIS
    }));
}
```

### 3. Tool wrapper (`wrapToolWithBeforeToolCallHook`)

In `runBeforeToolCallHook` (line ~96793), update the return type and the
wrapper to handle `result`:

```javascript
// Current code at line ~96813:
if (hookResult?.block) return {
    blocked: true,
    reason: hookResult.blockReason || "Tool call blocked by plugin hook"
};

// ADD after the block check:
if (hookResult?.result !== undefined) return {
    blocked: false,
    shortCircuit: true,
    result: hookResult.result,
    params: args.params
};
```

And in `wrapToolWithBeforeToolCallHook` (line ~96845):

```javascript
const outcome = await runBeforeToolCallHook({ toolName, params, toolCallId, ctx });
if (outcome.blocked) throw new Error(outcome.reason);

// ADD: short-circuit path
if (outcome.shortCircuit) return outcome.result;

// ... rest of normal execution
```

### 4. `after_tool_call` hook interaction

When a tool call is short-circuited, `after_tool_call` should still fire so
that observability plugins (logging, metrics) see every tool result. The event
should include a flag indicating the result was synthetic:

```typescript
// In after_tool_call event:
{
    toolName: "read",
    params: { file_path: "/foo/bar.ts" },
    result: "<cached content>",
    durationMs: 0,
    shortCircuited: true,   // NEW optional field
}
```

---

## Use Cases Beyond Caching

### Rate limiting
```typescript
api.on('before_tool_call', async (event) => {
    if (rateLimiter.isExceeded(event.toolName)) {
        return { block: true, blockReason: 'Rate limit exceeded for ' + event.toolName };
    }
});
```

### Audit logging
```typescript
api.on('before_tool_call', async (event, ctx) => {
    auditLog.record({
        tool: event.toolName,
        params: event.params,
        agent: ctx.agentId,
        session: ctx.sessionId,
        timestamp: Date.now(),
    });
    // return void — proceed normally
});
```

### Parameter validation / sanitization
```typescript
api.on('before_tool_call', async (event) => {
    if (event.toolName === 'bash' && event.params.command?.includes('rm -rf /')) {
        return { block: true, blockReason: 'Dangerous command blocked' };
    }
    if (event.toolName === 'read' && !event.params.file_path?.startsWith('/allowed/')) {
        return { params: { ...event.params, file_path: '/allowed/' + event.params.file_path } };
    }
});
```

### Mocking / testing
```typescript
api.on('before_tool_call', async (event) => {
    if (testMode && mockResponses[event.toolName]) {
        return { result: mockResponses[event.toolName](event.params) };
    }
});
```

### Cross-agent deduplication (AgentGlue)
```typescript
api.on('before_tool_call', async (event, ctx) => {
    if (SKIP_TOOLS.has(event.toolName)) return;

    const cached = await sidecarClient.cacheCheck(event.toolName, event.params);
    if (cached.hit) {
        return { result: `[cache hit, age=${cached.age_s}s]\n${cached.result}` };
    }
    // return void — proceed with normal execution, after_tool_call will cache it
});
```

---

## How AgentGlue Would Use It

With `result` short-circuiting, the entire AgentGlue plugin simplifies to:

```typescript
const agentGluePlugin = {
    id: 'openclaw-agentglue',
    name: 'AgentGlue',
    version: '0.5.0',

    register(api) {
        const client = new SidecarClient(cfg.host, cfg.port);

        // Single before_tool_call handler replaces ALL proxy tools
        api.on('before_tool_call', async (event, ctx) => {
            if (SKIP_TOOLS.has(event.toolName)) return;
            if (WRITE_TOOLS.has(event.toolName)) return; // writes handled in after_tool_call

            try {
                const cached = await client.cacheCheck(event.toolName, event.params);
                if (cached.hit) {
                    return { result: cached.result };
                }
            } catch {
                // sidecar down — fall through to normal execution
            }
        }, { priority: 100 }); // high priority: run early

        // after_tool_call: cache results + invalidate on writes (unchanged)
        api.on('after_tool_call', async (event, ctx) => {
            if (event.error) return;
            if (WRITE_TOOLS.has(event.toolName)) {
                try { await client.cacheInvalidate(READ_TOOL_NAMES); } catch {}
                return;
            }
            if (!event.result || SKIP_TOOLS.has(event.toolName)) return;
            if (event.shortCircuited) return; // don't re-cache our own results

            try {
                const result = typeof event.result === 'string'
                    ? event.result : JSON.stringify(event.result);
                await client.cacheStore(event.toolName, event.params, result,
                    cfg.cacheTTL, ctx?.agentId);
            } catch {}
        });

        // Lifecycle hooks (unchanged)
        api.on('gateway_start', async () => { /* start sidecar */ });
        api.on('gateway_stop', async () => { /* stop sidecar */ });

        // Only utility tools remain — no proxy tools needed
        api.registerTool(metricsToolDef);
        api.registerTool(healthToolDef);
    },
};
```

**What gets deleted:**
- All three `agentglue_cached_*` proxy tools (~80 lines)
- All Node.js fallback implementations (~60 lines)
- `BUILTIN_TOOL` and `SIDECAR_TOOL` mappings
- System prompt injection for tool preference
- Tool denial configuration for built-in `read`/`grep`/`glob`

---

## Backwards Compatibility

This change is fully backwards compatible:

1. **Type addition only** — `result` is optional; existing handlers that don't
   return it are unaffected.
2. **Accumulator extension** — `next.result ?? acc?.result` preserves
   existing behavior when no handler sets `result`.
3. **No breaking changes** to `block` or `params` semantics.
4. **`after_tool_call` still fires** — plugins relying on after_tool_call for
   logging/metrics continue to work. The new `shortCircuited` field is also
   optional.

---

## Performance Considerations

The `before_tool_call` hook already runs before every tool execution. Adding
`result` support does not introduce additional hook dispatches — it only adds a
field check in the wrapper:

```javascript
if (outcome.shortCircuit) return outcome.result;  // O(1) field check
```

For AgentGlue specifically:
- **Cache hit path:** sidecar HTTP roundtrip (~1-5ms on localhost) replaces
  actual tool execution (often 10-500ms). Net performance gain.
- **Cache miss path:** one extra sidecar HTTP call (~1-5ms overhead). Negligible
  compared to tool execution time.
- **Sidecar down path:** `catch {}` falls through immediately. No retry, no
  blocking.

The existing fast-path optimization (`if (!hookRunner?.hasHooks("before_tool_call"))`)
already skips all hook overhead when no plugin registers a handler.

---

## Open Questions

1. **Should `result` be `string` only or `string | unknown`?** Tool `execute()`
   returns `string` in the SDK, so `string` is the natural type. However, some
   internal tools return structured data that gets serialized. Recommend `string`
   for v1.

2. **Should short-circuited calls appear in loop detection?** The existing
   `recordToolCall` / `recordLoopOutcome` tracking should probably still run for
   short-circuited calls to prevent infinite cache-hit loops. The wrapper should
   call `recordLoopOutcome` with the short-circuited result.

3. **Should there be an opt-in mechanism?** Some tool authors may not want their
   tools to be short-circuitable (e.g., tools with side effects that look
   read-only). A tool-level `allowShortCircuit: false` flag could prevent
   `result` from being honored. Low priority for v1.

---

## Implementation Plan

1. **OpenClaw core PR:** Add `result` field to type + accumulator + wrapper
   (~30 lines changed across the source, auto-propagates to all bundle copies
   at build time).
2. **AgentGlue v0.5.0:** Rewrite to use `before_tool_call` with `result`,
   remove proxy tools, update tests and benchmarks.
3. **Documentation:** Update plugin hook docs to document the new field and
   short-circuit semantics.

---

## References

- OpenClaw CHANGELOG entries: #6570, #6660 (initial `before_tool_call`),
  #15012 (dual-path dispatch), #15635 (single-dispatch fix), #16852
  (wrapped-marker), #32360 (runId/toolCallId correlation)
- Current `PluginHookBeforeToolCallResult` type: `dist/plugin-sdk/plugins/types.d.ts:510-514`
- Hook dispatch: `runBeforeToolCall` in hook-runner, `wrapToolWithBeforeToolCallHook` in tool wrapper
- AgentGlue source: `/home/ubuntu/.openclaw/extensions/openclaw-agentglue/src/index.ts`
