#!/usr/bin/env python3
"""
AgentGlue Sidecar Server

HTTP server that wraps tools with AgentGlue middleware.
Receives tool calls from OpenClaw plugin via HTTP/JSON.
"""

import json
import sys
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Add AgentGlue to path (we're at openclaw-agentglue/sidecar/, go up to AgentGlue root)
SIDEcar_DIR = Path(__file__).resolve().parent
AGENTGLUE_ROOT = SIDEcar_DIR.parent.parent  # sidecar/ -> openclaw-agentglue/ -> AgentGlue/
sys.path.insert(0, str(AGENTGLUE_ROOT / "src"))

from agentglue import AgentGlue

# Initialize AgentGlue with middleware enabled
glue = AgentGlue(
    dedup=True,
    dedup_ttl=300.0,
    shared_memory=True,
    memory_ttl=600.0,
    rate_limiter=True,
    rate_limits={"search": 10.0},  # 10 calls/sec max
    record_events=True,
)


# Define tools with AgentGlue middleware
@glue.tool(name="search", ttl=60.0, rate_limit=10.0)
def search_tool(query: str) -> str:
    """
    Example search tool - in production this would call real APIs.
    Demonstrates AgentGlue deduplication, rate limiting, and metrics.
    """
    # Mock implementation - returns search-like results
    results = [
        f"Result 1: Information about '{query}' from source A",
        f"Result 2: Details on '{query}' from source B", 
        f"Result 3: Analysis of '{query}' from source C",
    ]
    return "\n".join(results)


@glue.tool(name="metrics")
def metrics_tool() -> str:
    """Return AgentGlue metrics report."""
    return glue.report()


class SidecarHandler(BaseHTTPRequestHandler):
    """HTTP request handler for tool calls."""

    def log_message(self, format, *args):
        """Suppress default logging - optional."""
        print(f"[Sidecar] {format % args}")

    def send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        """Handle GET requests - health check."""
        if self.path == "/health":
            from agentglue import __version__ as agentglue_version
            self.send_json({
                "status": "ok",
                "agentglue_version": agentglue_version,
                "tools": ["search", "metrics"]
            })
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        """Handle POST requests - tool calls."""
        if self.path != "/call":
            self.send_json({"error": "Not found"}, 404)
            return

        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self.send_json({"error": "Empty request body"}, 400)
            return

        body = self.rfile.read(content_length).decode()
        
        try:
            request = json.loads(body)
        except json.JSONDecodeError as e:
            self.send_json({"error": f"Invalid JSON: {e}"}, 400)
            return

        tool = request.get("tool")
        params = request.get("params", {})

        if not tool:
            self.send_json({"error": "Missing 'tool' field"}, 400)
            return

        # Route to appropriate tool
        try:
            if tool == "search":
                if "query" not in params:
                    self.send_json({"error": "Missing 'query' parameter"}, 400)
                    return
                result = search_tool(params["query"])
                self.send_json({"result": result})
            
            elif tool == "metrics":
                result = metrics_tool()
                self.send_json({"result": result})
            
            else:
                self.send_json({"error": f"Unknown tool: {tool}"}, 400)
        
        except Exception as e:
            self.send_json({"error": str(e)}, 500)


def run_server(port: int = 8765):
    """Start the sidecar HTTP server."""
    server = HTTPServer(("127.0.0.1", port), SidecarHandler)
    print(f"[AgentGlue Sidecar] Running on http://127.0.0.1:{port}")
    print(f"[AgentGlue Sidecar] Tools available: search, metrics")
    print(f"[AgentGlue Sidecar] Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[AgentGlue Sidecar] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AgentGlue Sidecar Server")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    args = parser.parse_args()
    
    run_server(args.port)
