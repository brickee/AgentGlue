#!/usr/bin/env python3
"""Tiny example: export AgentGlue recorder events to JSONL and inspect a summary."""

from __future__ import annotations

import json
from pathlib import Path

from agentglue import AgentGlue
from agentglue.core.recorder import summarize_jsonl

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "examples"
EVENT_PATH = ARTIFACT_DIR / "recorder_export.events.jsonl"


glue = AgentGlue(shared_memory=False, rate_limiter=False, task_lock=False, dedup_ttl=60.0)


@glue.tool(ttl=60.0)
def lookup(symbol: str) -> str:
    return f"definition:{symbol}"


lookup("AgentGlue", agent_id="agent-a")
lookup("AgentGlue", agent_id="agent-b")
lookup("Recorder", agent_id="agent-c")

exported = glue.export_events_jsonl(str(EVENT_PATH))
reloaded = summarize_jsonl(str(EVENT_PATH))

print("exported:")
print(json.dumps(exported, indent=2))
print()
print("reloaded:")
print(json.dumps(reloaded, indent=2))
