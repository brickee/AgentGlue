# Next TODO

## Immediate (next session)
1. Implement `ToolProxy` with exact-match dedup and TTL cache.
2. Add `@glue.tool()` decorator API.
3. Write smoke test: 3 agents calling same tool, verify dedup works.
4. Add basic metrics collection (calls total, calls saved, cache hits).

## Next up
5. Implement `SharedMemory` store with TTL and confidence.
6. Add semantic dedup (embedding-based similarity matching).
7. Write integration adapter skeleton for CrewAI.
8. Add summary report generator.
