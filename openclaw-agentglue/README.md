# OpenClaw AgentGlue Plugin

> Production-ready OpenClaw plugin that wraps AgentGlue middleware for intelligent tool coordination

[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](../AgentGlue)

## Features

- **🔧 Auto-managed Sidecar** - Python sidecar starts automatically, with health monitoring and crash recovery
- **🛡️ Deduplication** - Exact-match tool call deduplication prevents duplicate work
- **⏱️ Rate Limiting** - Per-tool rate limits protect external services
- **📁 Repo Exploration Tools** - Purpose-built tools for code repository analysis:
  - `deduped_search` - Search code patterns across repositories
  - `deduped_read_file` - Read files with pagination and caching
  - `deduped_list_files` - Explore directory structures
- **📊 Metrics & Observability** - Built-in metrics and health monitoring
- **🔄 Single-Flight** - Concurrent identical calls share one execution

## Installation

```bash
# Copy plugin to OpenClaw plugins directory
cp -r openclaw-agentglue ~/.openclaw/plugins/

# Or symlink for development
ln -s $(pwd)/openclaw-agentglue ~/.openclaw/plugins/openclaw-agentglue
```

## Requirements

- Node.js >= 18.0.0
- Python 3.10+
- AgentGlue (parent project)

## Quick Start

1. **Install dependencies:**
   ```bash
   cd openclaw-agentglue
   npm install
   npm run build
   ```

2. **Verify installation:**
   ```bash
   npm run verify
   ```

3. **Enable in OpenClaw:**
   The plugin auto-registers if placed in `~/.openclaw/plugins/`

## Configuration

Add to your OpenClaw config (`~/.openclaw/config.json`):

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
      "rateLimits": {
        "search": 10,
        "read_file": 20,
        "list_files": 15
      },
      "dedupTTL": 300,
      "sharedMemoryTTL": 600
    }
  }
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `host` | string | `127.0.0.1` | Sidecar host address |
| `port` | integer | `8765` | Sidecar port |
| `autoStart` | boolean | `true` | Auto-start sidecar on plugin load |
| `maxRestarts` | integer | `3` | Maximum sidecar restart attempts |
| `restartDelayMs` | integer | `2000` | Delay between restarts (ms) |
| `healthCheckIntervalMs` | integer | `30000` | Health check interval (ms) |
| `rateLimits` | object | `{search: 10, read_file: 20, list_files: 15}` | Per-tool rate limits (calls/sec) |
| `dedupTTL` | number | `300` | Deduplication cache TTL (seconds) |
| `sharedMemoryTTL` | number | `600` | Shared memory TTL (seconds) |

## Available Tools

### `agentglue_search`
Basic search with deduplication and metrics.

```json
{
  "query": "machine learning frameworks"
}
```

### `agentglue_metrics`
Get runtime metrics report.

```json
{}
```

### `deduped_search`
Search for files in a repository with deduplication.

```json
{
  "repo_path": "/path/to/repo",
  "pattern": "def.*train",
  "file_pattern": "*.py",
  "max_results": 50
}
```

**Parameters:**
- `repo_path` (required): Absolute path to repository root
- `pattern` (required): grep-compatible regex pattern
- `file_pattern`: Optional file glob (default: `*`)
- `max_results`: Maximum results to return (default: 50)

### `deduped_read_file`
Read file contents with deduplication and caching.

```json
{
  "file_path": "/path/to/file.py",
  "offset": 1,
  "limit": 200
}
```

**Parameters:**
- `file_path` (required): Absolute path to file
- `offset`: Line number to start from (1-indexed, default: 1)
- `limit`: Max lines to read (default: 200)

### `deduped_list_files`
List files in a directory with deduplication.

```json
{
  "dir_path": "/path/to/dir",
  "recursive": true,
  "include_hidden": false
}
```

**Parameters:**
- `dir_path` (required): Absolute path to directory
- `recursive`: List recursively (default: false)
- `include_hidden`: Include hidden files (default: false)

### `agentglue_health`
Get plugin and sidecar health status.

```json
{}
```

## Architecture

```
┌─────────────────┐     HTTP/JSON      ┌──────────────────┐
│  OpenClaw Core  │ ◄────────────────► │  AgentGlue       │
│                 │    Port 8765       │  Python Sidecar  │
└─────────────────┘                     └──────────────────┘
                                               │
                                               │ wraps with
                                               ▼
                                        ┌──────────────────┐
                                        │  AgentGlue       │
                                        │  Middleware      │
                                        │  - Dedup         │
                                        │  - Rate Limit    │
                                        │  - Metrics       │
                                        └──────────────────┘
```

## Troubleshooting

### Sidecar won't start
```bash
# Check Python availability
python3 --version

# Check AgentGlue is in Python path
cd /path/to/AgentGlue
python3 -c "from agentglue import AgentGlue; print('OK')"

# Manual sidecar test
python3 sidecar/server.py --port 8765
```

### Port already in use
```bash
# Find process using port
lsof -i :8765

# Kill it or change port in config
```

### Health check failures
- Check sidecar logs in console output
- Verify `autoStart: true` in config
- Ensure firewall allows localhost connections

### Build errors
```bash
# Clean and rebuild
rm -rf dist node_modules
npm install
npm run build
```

## Development

```bash
# Watch mode for development
npm run dev

# Run sidecar manually for testing
python3 sidecar/server.py --port 8765
```

## Cross-Platform Notes

- **Linux/macOS**: Full support
- **Windows**: WSL recommended; native support requires PowerShell adjustments

## License

MIT - See parent AgentGlue project
