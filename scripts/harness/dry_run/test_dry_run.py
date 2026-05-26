# SPDX-License-Identifier: Apache-2.0
"""End-to-end dry-run test: spawn fixture agents, aggregate, analyse, assert.

This is the **default-suite** smoke test for the research harness. No real
agent is spawned and no network is hit. It exists to make sure the schema,
the aggregator, and the analysis script stay in lockstep — if any one of
them drifts, this test fails before the harness is used to spend money on
real agents.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from scripts.harness import SCHEMA_VERSION
from scripts.harness.collect import load_rows as collect_load
from scripts.harness.collect import main as collect_main
from scripts.harness.conditions import load_conditions
from scripts.harness.run_condition import (
    DEFAULT_BRIEFS_DIR,
    DEFAULT_FIXTURES_DIR,
    run_cell,
)

EXPECTED_FIELDS = {
    "schema_version",
    "harness_version",
    "conditions_version",
    "cell_id",
    "factors",
    "run_idx",
    "seed",
    "model_id",
    "prompt_hash",
    "brief_path",
    "transport",
    "timestamp_utc",
    "duration_seconds",
    "spawned",
    "exit_code",
    "pr_url",
    "branch",
    "head_sha",
    "layer_picked",
    "lines_added",
    "lines_removed",
    "first_push_ci_status",
    "first_push_ci_green",
    "iterations_to_green",
    "claimed_ci_green",
    "final_message",
    "transcript_path",
    "description",
    "error",
}


@pytest.fixture
def small_run(tmp_path: Path) -> dict[str, Path]:
    """Run two cells × 4 replicates against the fixture transport."""
    spec = load_conditions()
    cells = list(spec.cells())
    chosen = cells[:2]
    assert len(chosen) == 2

    output_dir = tmp_path / "data"
    workdir_base = tmp_path / "work"
    for cell in chosen:
        run_cell(
            cell=cell,
            n=4,
            transport="fixture",
            output_dir=output_dir,
            briefs_dir=DEFAULT_BRIEFS_DIR,
            fixtures_dir=DEFAULT_FIXTURES_DIR,
            workdir_strategy="ephemeral",
            workdir_base=workdir_base,
            seed_base=20260526,
            timeout_seconds=60,
            skip_github=True,
        )
    return {"output_dir": output_dir, "cells_jsonl": output_dir}


def test_per_cell_jsonl_schema(small_run: dict[str, Path]) -> None:
    output_dir = small_run["output_dir"]
    jsonls = sorted(p for p in output_dir.glob("*.jsonl") if p.name != "all.jsonl")
    assert len(jsonls) == 2
    for path in jsonls:
        with path.open("r", encoding="utf-8") as fh:
            lines = [line for line in fh if line.strip()]
        assert len(lines) == 4
        for line in lines:
            row = json.loads(line)
            assert set(row.keys()) == EXPECTED_FIELDS, (
                f"unexpected schema in {path}: "
                f"missing={EXPECTED_FIELDS - row.keys()}, "
                f"extra={row.keys() - EXPECTED_FIELDS}"
            )
            assert row["schema_version"] == SCHEMA_VERSION
            assert row["transport"] == "fixture"
            assert isinstance(row["factors"], dict)
            assert row["prompt_hash"] and len(row["prompt_hash"]) == 16
            assert row["seed"] >= 0


def test_collect_aggregates_all_rows(small_run: dict[str, Path], tmp_path: Path) -> None:
    output_dir = small_run["output_dir"]
    all_jsonl = output_dir / "all.jsonl"
    rc = collect_main(["--input-dir", str(output_dir), "--output", str(all_jsonl)])
    assert rc == 0
    assert all_jsonl.exists()

    rows = collect_load([all_jsonl])
    assert len(rows) == 8  # 2 cells × 4 replicates
    # Aggregated file is sorted by (cell_id, run_idx); verify that contract.
    keys = [(r["cell_id"], r["run_idx"]) for r in rows]
    assert keys == sorted(keys)


def test_collect_refuses_schema_mismatch(small_run: dict[str, Path], tmp_path: Path) -> None:
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    bad_row = {
        "schema_version": SCHEMA_VERSION + 99,
        "cell_id": "ffffffffffff",
        "run_idx": 0,
    }
    (bad_dir / "ffffffffffff.jsonl").write_text(json.dumps(bad_row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        collect_load(list(bad_dir.glob("*.jsonl")))


@pytest.mark.skipif(
    importlib.util.find_spec("matplotlib") is None,
    reason="matplotlib not installed; install the `harness` extra to enable plotting tests.",
)
def test_analyze_produces_plots(small_run: dict[str, Path], tmp_path: Path) -> None:
    output_dir = small_run["output_dir"]
    all_jsonl = output_dir / "all.jsonl"
    collect_main(["--input-dir", str(output_dir), "--output", str(all_jsonl)])

    # Importing analyze lazily so the test is skip-clean when matplotlib is absent.
    from scripts.harness import analyze

    plots_dir = tmp_path / "plots"
    rc = analyze.main(["--input", str(all_jsonl), "--output-dir", str(plots_dir)])
    assert rc == 0
    for name in ("diversity_collapse.png", "calibration.png", "iteration_efficiency.png"):
        path = plots_dir / name
        assert path.exists(), f"missing plot: {path}"
        assert path.stat().st_size > 0, f"empty plot: {path}"


def test_analysis_pure_helpers_have_sane_shape() -> None:
    # Matplotlib-free helpers; safe to import even when the extra isn't installed.
    spec = importlib.util.find_spec("scripts.harness.analyze")
    assert spec is not None
    from scripts.harness import analyze

    rows = [
        {
            "layer_picked": "trust",
            "claimed_ci_green": True,
            "first_push_ci_green": True,
            "iterations_to_green": 1,
            "factors": {"model": "opus"},
        },
        {
            "layer_picked": "trust",
            "claimed_ci_green": True,
            "first_push_ci_green": False,
            "iterations_to_green": 4,
            "factors": {"model": "opus"},
        },
        {
            "layer_picked": "identity",
            "claimed_ci_green": False,
            "first_push_ci_green": False,
            "iterations_to_green": None,
            "factors": {"model": "opus"},
        },
    ]
    div = analyze.diversity_collapse_metrics(rows)
    assert div["n"] == 3
    assert abs(div["top1"] - 2 / 3) < 1e-9

    cal = analyze.calibration_metrics(rows)
    assert abs(cal["claimed"] - 2 / 3) < 1e-9
    assert abs(cal["actual"] - 1 / 3) < 1e-9

    dist = analyze.iteration_distribution(rows)
    assert sorted(dist) == [1, 4]


def test_module_layout_is_importable() -> None:
    # Belt-and-braces: make sure the package shows up under its expected name.
    assert "scripts.harness" in sys.modules or importlib.util.find_spec("scripts.harness")
