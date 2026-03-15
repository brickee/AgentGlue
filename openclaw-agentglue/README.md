# OpenClaw AgentGlue Plugin

Bridge between OpenClaw and AgentGlue middleware. This plugin allows OpenClaw to use tools wrapped with AgentGlue's deduplication, rate limiting, and metrics collection.

## Structure

```
openclaw-agentglue/
├── openclaw.plugin.json    # Plugin manifest for OpenClaw
├── package.json            # NPM package definition
├── tsconfig.json           # TypeScript configuration
├── README.md               # This file
├── src/
│   └── index.ts            # Plugin entry point (TypeScript)
└── sidecar/
    ├── server.py           # Python HTTP sidecar wrapping AgentGlue
    └── requirements.txt    # Python dependencies
```

## How It Works

1. **OpenClaw Plugin** (`src/index.ts`): TypeScript plugin that receives tool calls from OpenClaw and forwards them via HTTP to the Python sidecar.

2. **AgentGlue Sidecar** (`sidecar/server.py`): Python HTTP server that wraps tools with AgentGlue middleware (dedup, rate limiting, metrics).

3. **Communication**: Node.js ↔ Python via HTTP/JSON on localhost:8765

## Installation

### 1. Build the Plugin

```bash
cd openclaw-agentglue
npm install
npm run build
```

### 2. Install in OpenClaw

For local development, link the plugin:

```bash
# In OpenClaw plugins directory (adjust path as needed)
openclaw plugin install /path/to/AgentGlue/openclaw-agentglue
```

Or manually copy/symlink the `openclaw-agentglue` folder to your OpenClaw plugins directory.

### 3. Start the Sidecar

The sidecar must be running for the plugin to work:

```bash
cd openclaw-agentglue
python3 sidecar/server.py
```

For production, the plugin should auto-start the sidecar (TODO in Stage 2).

## Usage

Once installed and the sidecar is running:

```
/agentglue_search query="machine learning papers"
/agentglue_metrics
```

## Tools

### `agentglue_search`

Search with AgentGlue middleware (deduplication, rate limiting, metrics).

**Parameters:**
- `query` (string, required): Search query

### `agentglue_metrics`

Get runtime metrics from AgentGlue.

## Development

### Rebuild after changes

```bash
npm run build
```

### Test sidecar directly

```bash
# Start sidecar
python3 sidecar/server.py

# In another terminal, test with curl:
curl -X POST http://localhost:8765/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "search", "params": {"query": "test"}}'

# Check health:
curl http://localhost:8765/health
```

## Architecture

```
┌─────────────┐     HTTP/JSON      ┌─────────────┐     Function Call    ┌─────────┐
│  OpenClaw   │ ◄────────────────► │   Sidecar   │ ◄──────────────────► │  Tool   │
│   Plugin    │    (port 8765)     │   (Python)  │  (AgentGlue wrap)    │  (Python)│
│  (Node.js)  │                    │             │                      │         │
└─────────────┘                    └─────────────┘                      └─────────┘
```

## Stage 1 Complete

✅ Minimal plugin skeleton  
✅ Python sidecar prototype  
✅ HTTP/JSON bridge working  
✅ Tool endpoint exposed  

## Next (Stage 2)

- Auto-start/stop sidecar from plugin
- Health check and reconnection
- Configuration management
- More tool integrations
