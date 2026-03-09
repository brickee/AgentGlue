"""Event recording and duplicate detection.

Ported from AgentGym's replay module. Used for observability and
post-hoc analysis of multi-agent coordination.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


class EventRecorder:
    """Records events to an append-only log."""

    def __init__(self):
        self.events: List[Dict] = []

    def record(self, event_dict: Dict) -> None:
        self.events.append(event_dict)

    def dump_jsonl(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            for e in self.events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def clear(self) -> None:
        self.events.clear()


def load_jsonl(path: str) -> List[Dict]:
    p = Path(path)
    out: List[Dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            out.append(json.loads(line))
    return out


def detect_duplicates(events: List[Dict]) -> Dict[str, Dict]:
    """Detect duplicate tool calls across agents.

    Groups tool calls by (tool_name, args_hash) intent.
    Returns duplicate counts by agent and by tool.
    """
    intent_map: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)

    for e in events:
        if e.get("event_type") != "tool_call":
            continue
        tool_name = e.get("tool_name", "")
        args_hash = e.get("payload", {}).get("args_hash", "")
        intent_map[(tool_name, args_hash)].append(e)

    by_agent: Dict[str, int] = defaultdict(int)
    by_tool: Dict[str, int] = defaultdict(int)
    total_saved = 0

    for (tool_name, _), calls in intent_map.items():
        if len(calls) > 1:
            duplicates = len(calls) - 1
            total_saved += duplicates
            by_tool[tool_name] += duplicates
            for call in calls[1:]:
                agent = call.get("agent_id", "unknown")
                by_agent[agent] += duplicates

    return {
        "by_agent": dict(by_agent),
        "by_tool": dict(by_tool),
        "total_duplicates": total_saved,
    }
