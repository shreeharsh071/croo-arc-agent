"""
solve_offline.py — run the solver against a local JSON file with no
network access and no CAP credentials. Useful for quickly checking the
solver's behavior on a puzzle before spending real USDC testing the
on-chain flow.

Usage:
    python -m croo_arc_agent.solve_offline examples/sample_task.json
"""

from __future__ import annotations

import json
import sys

from .solver import solve_task


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m croo_arc_agent.solve_offline <path-to-task.json>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    with open(path) as f:
        data = json.load(f)

    # Accept either a bare task ({"train":..., "test":...}) or the
    # demo's wrapped format ({"task": {...}, "expected_test_output": ...})
    task = data["task"] if "task" in data else data
    expected = data.get("expected_test_output")

    result = solve_task(task)
    print(json.dumps(
        {
            "predictions": result.predictions,
            "strategy_used": result.strategy_used,
            "confidence": result.confidence,
            "reasoning_hash": result.reasoning_hash,
            "notes": result.notes,
        },
        indent=2,
    ))

    if expected is not None:
        verdict = "CORRECT" if result.predictions == expected else "INCORRECT"
        print(f"\nverification against known answer: {verdict}")


if __name__ == "__main__":
    main()
