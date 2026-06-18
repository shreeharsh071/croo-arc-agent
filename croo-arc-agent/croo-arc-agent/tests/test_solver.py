"""
Unit tests for croo_arc_agent.solver — run with: pytest tests/
These require no network access and no CAP credentials; they only
exercise the pure-Python puzzle-solving logic.
"""

import json
import pathlib

import pytest

from croo_arc_agent.solver import solve_task

SAMPLE_TASK_PATH = pathlib.Path(__file__).resolve().parent.parent / "examples" / "sample_task.json"


def test_flip_vertical_strategy():
    task = {
        "train": [
            {"input": [[1, 2]], "output": [[1, 2]]},
        ],
        "test": [{"input": [[3, 4]]}],
    }
    result = solve_task(task)
    assert result.predictions == [[[3, 4]]]
    assert result.strategy_used == "identity"
    assert result.confidence > 0.9


def test_color_remap_strategy():
    task = {
        "train": [
            {"input": [[1, 1], [2, 2]], "output": [[3, 3], [4, 4]]},
            {"input": [[2, 1], [1, 2]], "output": [[4, 3], [3, 4]]},
        ],
        "test": [{"input": [[1, 2], [2, 1]]}],
    }
    result = solve_task(task)
    assert result.predictions == [[[3, 4], [4, 3]]]
    assert result.strategy_used == "color_remap"


def test_tile_strategy():
    task = {
        "train": [{"input": [[1, 2]], "output": [[1, 2, 1, 2]]}],
        "test": [{"input": [[3, 4]]}],
    }
    result = solve_task(task)
    assert result.predictions == [[[3, 4, 3, 4]]]
    assert result.strategy_used == "tile"


def test_reasoning_hash_is_deterministic():
    task = {
        "train": [{"input": [[1, 2]], "output": [[2, 1]]}],
        "test": [{"input": [[3, 4]]}],
    }
    r1 = solve_task(task)
    r2 = solve_task(task)
    assert r1.reasoning_hash == r2.reasoning_hash, "same task must yield same proof hash"


def test_invalid_task_raises():
    with pytest.raises(ValueError):
        solve_task({"train": []})
    with pytest.raises(ValueError):
        solve_task({"train": [{"input": [[1]], "output": [[1]]}], "test": []})


def test_sample_task_file_matches_known_answer():
    data = json.loads(SAMPLE_TASK_PATH.read_text())
    result = solve_task(data["task"])
    assert result.predictions == data["expected_test_output"]
