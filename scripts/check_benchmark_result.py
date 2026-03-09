#!/usr/bin/env python3
"""Lightweight sanity checks for AgentGlue benchmark artifacts.

This is intentionally small and local: it validates that a benchmark result.json
looks internally consistent enough to trust during development, without turning
benchmarking into a brittle CI ceremony.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_scenario(name: str, payload: Dict[str, Any]) -> None:
    baseline_runs = payload["runs"]["baseline"]
    glue_runs = payload["runs"]["agentglue"]
    expect(len(baseline_runs) == len(glue_runs), f"{name}: baseline/glue run counts differ")

    plan_calls = payload["plan_summary"]["observed_calls_per_run"]
    baseline_agg = payload["aggregate"]["baseline"]
    glue_agg = payload["aggregate"]["agentglue"]

    expect(baseline_agg["observed_tool_calls_mean"] == plan_calls, f"{name}: baseline observed mean != planned calls")
    expect(glue_agg["observed_tool_calls_mean"] == plan_calls, f"{name}: glue observed mean != planned calls")
    expect(glue_agg["underlying_executions_mean"] <= baseline_agg["underlying_executions_mean"], f"{name}: glue underlying executions exceed baseline")
    expect(glue_agg["calls_saved_mean"] >= 0, f"{name}: negative calls_saved_mean")
    expect(0.0 <= glue_agg["dedup_rate_mean"] <= 1.0, f"{name}: dedup_rate_mean outside [0,1]")
    expect(0.0 <= glue_agg["cache_hit_rate_mean"] <= 1.0, f"{name}: cache_hit_rate_mean outside [0,1]")

    for run in glue_runs:
        summary = run["summary"]
        expect(summary["tool_calls_total"] == run["observed_tool_calls"], f"{name}: tool_calls_total != observed_tool_calls")
        expect(summary["tool_calls_underlying"] == run["underlying_executions"], f"{name}: underlying metric mismatch")
        expect(summary["calls_saved"] == run["observed_tool_calls"] - run["underlying_executions"], f"{name}: calls_saved mismatch")
        expect(run["duplicate_analysis"]["total_duplicates"] == summary["tool_calls_deduped"], f"{name}: duplicate analysis mismatch vs deduped metric")

        per_tool = run["per_tool_summary"]
        observed_sum = sum(tool["observed_calls"] for tool in per_tool.values())
        underlying_sum = sum(tool["underlying_executions"] for tool in per_tool.values())
        expect(observed_sum == run["observed_tool_calls"], f"{name}: per-tool observed sum mismatch")
        expect(underlying_sum == run["underlying_executions"], f"{name}: per-tool underlying sum mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json", help="Path to artifacts/.../result.json")
    args = parser.parse_args()

    result_path = Path(args.result_json)
    data = json.loads(result_path.read_text(encoding="utf-8"))

    for scenario_name, payload in data["scenarios"].items():
        check_scenario(scenario_name, payload)

    probe = data["concurrent_probe"]
    summary = probe["summary"]
    expect(probe["underlying_call_count"] == 1, "concurrent probe should have exactly one underlying call")
    expect(summary["tool_calls_underlying"] == 1, "concurrent probe metrics should show one underlying call")
    expect(summary["tool_calls_coalesced"] >= 1, "concurrent probe should show at least one coalesced call")
    expect(summary["tool_calls_deduped"] >= summary["tool_calls_coalesced"], "deduped count should cover coalesced calls")

    print(json.dumps({
        "ok": True,
        "checked": str(result_path),
        "scenario_count": len(data["scenarios"]),
        "concurrent_probe_underlying": probe["underlying_call_count"],
    }, indent=2))


if __name__ == "__main__":
    main()
