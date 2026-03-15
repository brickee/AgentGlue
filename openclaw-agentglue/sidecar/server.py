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


@glue.tool(name="deduped_search", ttl=30.0, rate_limit=5.0)
def deduped_search_tool(
    repo_path: str,
    pattern: str,
    file_pattern: str = "*",
    max_results: int = 50
) -> str:
    """
    Search for files in a repository with deduplication.
    Uses grep for fast pattern matching with file filtering.
    """
    import subprocess
    import os

    if not os.path.isdir(repo_path):
        return f"Error: Directory not found: {repo_path}"

    try:
        # Build grep command
        cmd = ['grep', '-r', '-n', '--include', file_pattern, '-l', pattern, repo_path]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 1:  # No matches
            return f"No files found matching pattern '{pattern}' in {repo_path}"

        if result.returncode != 0:
            return f"Search error: {result.stderr}"

        files = result.stdout.strip().split('\n')[:max_results]

        if not files or files == ['']:
            return f"No files found matching pattern '{pattern}'"

        # Get line counts for context
        output_lines = [f"Found {len(files)} file(s) matching '{pattern}':\n"]
        for f in files:
            # Get matching lines with context
            line_cmd = ['grep', '-n', '-C', '2', pattern, f]
            line_result = subprocess.run(line_cmd, capture_output=True, text=True, timeout=10)
            matches = line_result.stdout.strip() if line_result.returncode == 0 else "(error reading file)"
            # Truncate long outputs
            if len(matches) > 500:
                matches = matches[:500] + "...\n[truncated]"
            output_lines.append(f"\n=== {f} ===\n{matches}")

        return '\n'.join(output_lines)

    except subprocess.TimeoutExpired:
        return "Error: Search timed out (30s limit)"
    except Exception as e:
        return f"Error during search: {str(e)}"


@glue.tool(name="deduped_read_file", ttl=60.0, rate_limit=10.0)
def deduped_read_file_tool(
    file_path: str,
    offset: int = 1,
    limit: int = 200
) -> str:
    """
    Read file contents with deduplication and caching.
    Supports pagination via offset and limit parameters.
    """
    from pathlib import Path

    path = Path(file_path)

    if not path.exists():
        return f"Error: File not found: {file_path}"

    if not path.is_file():
        return f"Error: Path is not a file: {file_path}"

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        total_lines = len(lines)
        start = max(0, offset - 1)  # Convert to 0-indexed
        end = min(start + limit, total_lines)

        selected_lines = lines[start:end]
        content = ''.join(selected_lines)

        # Build response
        header = f"File: {file_path}\nLines: {start + 1}-{end} of {total_lines}\n{'='*50}\n"

        # Add line numbers
        numbered_lines = []
        for i, line in enumerate(selected_lines, start=start + 1):
            numbered_lines.append(f"{i:4d}: {line}")

        return header + ''.join(numbered_lines)

    except Exception as e:
        return f"Error reading file: {str(e)}"


@glue.tool(name="deduped_list_files", ttl=10.0, rate_limit=5.0)
def deduped_list_files_tool(
    dir_path: str,
    recursive: bool = False,
    include_hidden: bool = False
) -> str:
    """
    List files in a directory with deduplication.
    Supports recursive listing and hidden file filtering.
    """
    from pathlib import Path

    path = Path(dir_path)

    if not path.exists():
        return f"Error: Directory not found: {dir_path}"

    if not path.is_dir():
        return f"Error: Path is not a directory: {dir_path}"

    try:
        if recursive:
            items = list(path.rglob('*'))
        else:
            items = list(path.iterdir())

        # Filter hidden files
        if not include_hidden:
            items = [i for i in items if not i.name.startswith('.')]

        # Sort: directories first, then files
        items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

        lines = [f"Directory: {dir_path}{' (recursive)' if recursive else ''}\n{'='*50}\n"]

        for item in items:
            prefix = "📁 " if item.is_dir() else "📄 "
            suffix = "/" if item.is_dir() else ""
            rel_path = item.relative_to(path)
            lines.append(f"{prefix}{rel_path}{suffix}")

        lines.append(f"\nTotal: {len(items)} items")

        return '\n'.join(lines)

    except Exception as e:
        return f"Error listing directory: {str(e)}"


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
                "tools": [
                    "search",
                    "metrics",
                    "deduped_search",
                    "deduped_read_file",
                    "deduped_list_files"
                ]
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

            elif tool == "deduped_search":
                required = ["repo_path", "pattern"]
                missing = [r for r in required if r not in params]
                if missing:
                    self.send_json({"error": f"Missing required parameters: {missing}"}, 400)
                    return
                result = deduped_search_tool(
                    params["repo_path"],
                    params["pattern"],
                    params.get("file_pattern", "*"),
                    params.get("max_results", 50)
                )
                self.send_json({"result": result})

            elif tool == "deduped_read_file":
                if "file_path" not in params:
                    self.send_json({"error": "Missing 'file_path' parameter"}, 400)
                    return
                result = deduped_read_file_tool(
                    params["file_path"],
                    params.get("offset", 1),
                    params.get("limit", 200)
                )
                self.send_json({"result": result})

            elif tool == "deduped_list_files":
                if "dir_path" not in params:
                    self.send_json({"error": "Missing 'dir_path' parameter"}, 400)
                    return
                result = deduped_list_files_tool(
                    params["dir_path"],
                    params.get("recursive", False),
                    params.get("include_hidden", False)
                )
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
