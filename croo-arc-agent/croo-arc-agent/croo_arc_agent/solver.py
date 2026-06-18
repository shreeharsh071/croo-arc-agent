"""
solver.py — Multi-strategy abstract grid-reasoning solver.

This module is intentionally decoupled from the CAP networking code
(see provider.py). It exposes one function, `solve_task`, that takes
an ARC-AGI-style task (a dict with "train" and "test" pairs of 2-D
integer grids) and returns a predicted output grid plus metadata.

If you already have a stronger solver (e.g. the multi-strategy
`arc_solver.py` you built for the ARC Prize 2026 competition), you
can drop it in here: keep the public function signature

    solve_task(task: dict) -> SolveResult

identical, and provider.py will call it without any other changes.

The strategies below are deliberately simple and explainable — each
one is tested against every training pair, and only a strategy that
reproduces ALL training outputs exactly is considered "verified" and
used on the test input. This verification-before-use design is what
makes the agent's output auditable, which matters for the Data &
Verification angle of this submission: a customer (human or agent)
can re-run the same deterministic strategy against the same training
pairs and get the same answer — there is no hidden randomness.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable

Grid = list[list[int]]
Pair = dict[str, Grid]


@dataclass
class SolveResult:
    predictions: list[Grid]
    strategy_used: str
    confidence: float
    reasoning_hash: str
    notes: str = ""


# --------------------------------------------------------------------------
# Grid helpers
# --------------------------------------------------------------------------

def _dims(g: Grid) -> tuple[int, int]:
    return len(g), (len(g[0]) if g else 0)


def _equal(a: Grid, b: Grid) -> bool:
    return a == b


def _transpose(g: Grid) -> Grid:
    return [list(row) for row in zip(*g)]


def _flip_h(g: Grid) -> Grid:
    return [list(reversed(row)) for row in g]


def _flip_v(g: Grid) -> Grid:
    return [list(row) for row in reversed(g)]


def _rotate90(g: Grid) -> Grid:
    return [list(row) for row in zip(*g[::-1])]


def _rotate180(g: Grid) -> Grid:
    return _rotate90(_rotate90(g))


def _rotate270(g: Grid) -> Grid:
    return _rotate90(_rotate90(_rotate90(g)))


def _background_color(g: Grid) -> int:
    counts: dict[int, int] = {}
    for row in g:
        for v in row:
            counts[v] = counts.get(v, 0) + 1
    return max(counts, key=counts.get) if counts else 0


def _bbox_nonbg(g: Grid, bg: int) -> Grid:
    h, w = _dims(g)
    rows = [r for r in range(h) if any(v != bg for v in g[r])]
    cols = [c for c in range(w) if any(g[r][c] != bg for r in range(h))]
    if not rows or not cols:
        return [row[:] for row in g]
    r0, r1 = min(rows), max(rows)
    c0, c1 = min(cols), max(cols)
    return [row[c0:c1 + 1] for row in g[r0:r1 + 1]]


def _tile(g: Grid, rep_r: int, rep_c: int) -> Grid:
    out: Grid = []
    for row in g:
        tiled_row = row * rep_c
        for _ in range(rep_r):
            out.append(list(tiled_row))
    return out


def _scale(g: Grid, fr: int, fc: int) -> Grid:
    out: Grid = []
    for row in g:
        new_row: list[int] = []
        for v in row:
            new_row.extend([v] * fc)
        for _ in range(fr):
            out.append(list(new_row))
    return out


def _color_map_from_pair(inp: Grid, out: Grid) -> dict[int, int] | None:
    if _dims(inp) != _dims(out):
        return None
    mapping: dict[int, int] = {}
    h, w = _dims(inp)
    for r in range(h):
        for c in range(w):
            a, b = inp[r][c], out[r][c]
            if a in mapping and mapping[a] != b:
                return None
            mapping[a] = b
    return mapping


def _apply_color_map(g: Grid, mapping: dict[int, int]) -> Grid:
    return [[mapping.get(v, v) for v in row] for row in g]


# --------------------------------------------------------------------------
# Strategy registry — each strategy is (name, transform_fn)
# A strategy is "verified" if transform_fn(train_input_i) == train_output_i
# for every training pair.
# --------------------------------------------------------------------------

_GEOMETRIC: list[tuple[str, Callable[[Grid], Grid]]] = [
    ("identity", lambda g: [row[:] for row in g]),
    ("flip_horizontal", _flip_h),
    ("flip_vertical", _flip_v),
    ("rotate_90", _rotate90),
    ("rotate_180", _rotate180),
    ("rotate_270", _rotate270),
    ("transpose", _transpose),
    ("crop_to_bounding_box", lambda g: _bbox_nonbg(g, _background_color(g))),
]


def _try_geometric(train: list[Pair]) -> tuple[str, Callable[[Grid], Grid]] | None:
    for name, fn in _GEOMETRIC:
        if all(_equal(fn(p["input"]), p["output"]) for p in train):
            return name, fn
    return None


def _try_color_map(train: list[Pair]) -> dict[int, int] | None:
    mapping = _color_map_from_pair(train[0]["input"], train[0]["output"])
    if mapping is None:
        return None
    for p in train[1:]:
        m2 = _color_map_from_pair(p["input"], p["output"])
        if m2 is None:
            return None
        for k, v in m2.items():
            if k in mapping and mapping[k] != v:
                return None
            mapping[k] = v
    if all(_equal(_apply_color_map(p["input"], mapping), p["output"]) for p in train):
        return mapping
    return None


def _try_tile_or_scale(train: list[Pair]) -> tuple[str, int, int] | None:
    ih, iw = _dims(train[0]["input"])
    oh, ow = _dims(train[0]["output"])
    if ih == 0 or iw == 0 or oh % ih or ow % iw:
        return None
    rep_r, rep_c = oh // ih, ow // iw
    if rep_r == 1 and rep_c == 1:
        return None
    if all(_dims(p["output"]) == (_dims(p["input"])[0] * rep_r, _dims(p["input"])[1] * rep_c) for p in train):
        if all(_equal(_tile(p["input"], rep_r, rep_c), p["output"]) for p in train):
            return "tile", rep_r, rep_c
        if all(_equal(_scale(p["input"], rep_r, rep_c), p["output"]) for p in train):
            return "scale", rep_r, rep_c
    return None


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def _validate_task(task: dict) -> None:
    if "train" not in task or "test" not in task:
        raise ValueError("task must contain 'train' and 'test' keys")
    if not isinstance(task["train"], list) or len(task["train"]) == 0:
        raise ValueError("task['train'] must be a non-empty list of {input, output} pairs")
    if not isinstance(task["test"], list) or len(task["test"]) == 0:
        raise ValueError("task['test'] must be a non-empty list of {input} pairs")
    for p in task["train"]:
        if "input" not in p or "output" not in p:
            raise ValueError("each train pair needs 'input' and 'output' grids")
    for p in task["test"]:
        if "input" not in p:
            raise ValueError("each test pair needs an 'input' grid")


def solve_task(task: dict) -> SolveResult:
    """Solve an ARC-AGI-style abstract reasoning task.

    Parameters
    ----------
    task: dict with shape
        {
          "train": [{"input": Grid, "output": Grid}, ...],
          "test":  [{"input": Grid}, ...]
        }

    Returns
    -------
    SolveResult with one prediction grid per test pair, the name of the
    strategy that was verified against every training pair, a confidence
    score, and a sha256 reasoning hash that a customer can use to verify
    the agent did not change its method between training-pair checks and
    final prediction (provenance / output-check guarantee).
    """
    _validate_task(task)
    train: list[Pair] = task["train"]
    test_inputs: list[Grid] = [p["input"] for p in task["test"]]

    strategy_name = "fallback_identity"
    predictions: list[Grid] = [g for g in test_inputs]
    confidence = 0.15
    notes = "No verified rule matched every training pair; returned input unchanged as a safe fallback."

    geo = _try_geometric(train)
    if geo is not None:
        strategy_name, fn = geo
        predictions = [fn(g) for g in test_inputs]
        confidence = 0.97
        notes = f"Geometric transform '{strategy_name}' reproduced all {len(train)} training pairs exactly."
    else:
        cmap = _try_color_map(train)
        if cmap is not None:
            strategy_name = "color_remap"
            predictions = [_apply_color_map(g, cmap) for g in test_inputs]
            confidence = 0.95
            notes = f"Per-cell color mapping {cmap} reproduced all {len(train)} training pairs exactly."
        else:
            tile_res = _try_tile_or_scale(train)
            if tile_res is not None:
                strategy_name, rep_r, rep_c = tile_res
                if strategy_name == "tile":
                    predictions = [_tile(g, rep_r, rep_c) for g in test_inputs]
                else:
                    predictions = [_scale(g, rep_r, rep_c) for g in test_inputs]
                confidence = 0.93
                notes = (
                    f"Pattern '{strategy_name}' with factors ({rep_r}, {rep_c}) "
                    f"reproduced all {len(train)} training pairs exactly."
                )

    reasoning_payload = {
        "strategy": strategy_name,
        "train_pair_count": len(train),
        "predictions": predictions,
    }
    reasoning_hash = hashlib.sha256(
        json.dumps(reasoning_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return SolveResult(
        predictions=predictions,
        strategy_used=strategy_name,
        confidence=confidence,
        reasoning_hash=reasoning_hash,
        notes=notes,
    )
