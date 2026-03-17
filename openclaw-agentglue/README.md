# OpenClaw AgentGlue Plugin

> OpenClaw plugin for cross-process, cross-agent deduplicated caching via a lightweight Python sidecar backed by SQLite.

[![npm version](https://img.shields.io/npm/v/openclaw-agentglue.svg)](https://www.npmjs.com/package/openclaw-agentglue)

## What changed in v0.3

v0.3 turns the plugin into a self-contained npm package with cross-process caching:
- Bundles the AgentGlue Python library inside the package
- Uses a SQLite-backed sidecar for cross-process cache sharing
- Auto-caches tool results after read-only calls via `after_tool_call` hook
- Exposes cache-aware OpenClaw tools for repo exploration and file reads

No separate parent-project checkout or `pip install` is required at runtime.

## Performance

Tested across 8 multi-agent scenarios (123 total tool calls):

| Metric | Value |
|---|---|
| Overall speedup | **3.7x** |
| Time saved | **73%** (866ms → 235ms) |
| Cache hit rate | **76%** (94/123) |
| Cache check latency | **0.6ms** median |
| Best case (10 agents) | **5.0x** speedup, 85% hit rate |
| Search operations | **6.8x** speedup |

More agents and more overlapping work = bigger wins. Zero overhead when there's no overlap.

See [benchmark details](../README.md#benchmark-no-glue-vs-with-glue) in the main README.

## Features

- **SQLite-backed cross-agent cache** — cache survives across processes and agent sessions
- **Auto-managed sidecar** — starts automatically, includes health checks and restart handling
- **Exact-match dedup** — identical tool calls collapse to a shared cached result
- **`after_tool_call` hook** — auto-caches all read-only tool results (no agent changes needed)
- **Cache-aware repo tools** — read/search/list helpers for code exploration
- **Metrics + health endpoints** — inspect cache behavior and runtime status
- **Self-contained package** — bundled Python library, no extra AgentGlue install needed

## Install

Preferred:

```bash
npm install -g openclaw-agentglue
# or
openclaw plugins install openclaw-agentglue
```

For local development:

```bash
cd openclaw-agentglue
npm install
npm run build
npm run verify
```

## Requirements

- Node.js >= 18
- Python 3.10+
- OpenClaw with plugin support

## OpenClaw configuration

Add this to your OpenClaw config:

```json
{
  "plugins": {
    "openclaw-agentglue": {
      "host": "127.0.0.1",
      "port": 8765,
      "autoStart": true,
      "maxRestarts": 3,
      "restartDelayMs": 2000,
      "healthCheckIntervalMs": 30000,
      "cacheTTL": 300,
      "dbPath": ""
    }
  }
}
```

### Config options

| Option | Type | Default | Description |
|---|---|---:|---|
| `host` | string | `127.0.0.1` | Sidecar host to bind/connect to |
| `port` | integer | `8765` | Sidecar port |
| `autoStart` | boolean | `true` | Start sidecar automatically on gateway startup |
| `maxRestarts` | integer | `3` | Max automatic restart attempts |
| `restartDelayMs` | integer | `2000` | Delay between restart attempts |
| `healthCheckIntervalMs` | integer | `30000` | Sidecar health probe interval |
| `cacheTTL` | number | `300` | TTL in seconds for auto-cached tool results |
| `dbPath` | string | `""` | Optional SQLite DB path; empty uses `~/.openclaw/cache/agentglue.db` |

## Exposed OpenClaw tools

These are the tools OpenClaw users/agents actually call:

### `agentglue_cached_read`
Read a file with cross-agent cache lookup first.

```json
{
  "file_path": "/abs/path/to/file.py",
  "offset": 1,
  "limit": 200
}
```

### `agentglue_cached_search`
Search a repository with cache lookup first.

```json
{
  "repo_path": "/abs/path/to/repo",
  "pattern": "def.*train",
  "file_pattern": "*.py",
  "max_results": 50
}
```

### `agentglue_cached_list`
List files in a directory with cache lookup first.

```json
{
  "dir_path": "/abs/path/to/dir",
  "recursive": true,
  "include_hidden": false
}
```

### `agentglue_metrics`
Return cache and middleware metrics.

```json
{}
```

### `agentglue_health`
Return sidecar health and runtime config summary.

```json
{}
```

## Internal sidecar tools

The Python sidecar also defines internal tools (`deduped_read_file`, `deduped_search`, `deduped_list_files`) which back the public `agentglue_cached_*` tools. In normal OpenClaw usage, call the `agentglue_cached_*` names.

## Architecture

```text
OpenClaw gateway
  └─ AgentGlue plugin (TypeScript)
      ├─ after_tool_call hook stores cached results
      ├─ registers agentglue_cached_* tools
      └─ manages Python sidecar lifecycle
             └─ SQLite-backed AgentGlue runtime
```

## Running the benchmark

From the parent AgentGlue repo:

```bash
# Full 100-test suite with baseline comparison report
PYTHONPATH=src python3 -m pytest tests/test_sidecar_benchmark.py -v -s

# Standalone mode (no pytest needed)
PYTHONPATH=src python3 tests/test_sidecar_benchmark.py
```

The `TestBaselineComparison` test class runs identical workloads with and without cache, printing a side-by-side latency comparison table.

## Verify before release

```bash
npm run build
npm run verify
npm pack --dry-run
```

## Troubleshooting

### Sidecar does not start
```bash
python3 --version
python3 sidecar/server.py --host 127.0.0.1 --port 8765
```

### Port conflict
```bash
lsof -i :8765
```

### Clean rebuild
```bash
rm -rf dist node_modules python
npm install
npm run build
npm run verify
```

## License

MIT
