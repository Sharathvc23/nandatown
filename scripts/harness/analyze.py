# SPDX-License-Identifier: Apache-2.0
"""Plot the three core research metrics from an aggregated dataset.

Inputs: ``data/hackathon-runs/all.jsonl`` (or any path passed via ``--input``).
Outputs three PNGs in ``--output-dir`` (default: ``data/hackathon-runs``):

* ``diversity_collapse.png``  — top-1 / top-3 layer cluster share per condition.
* ``calibration.png``         — claimed-CI-green vs actual-CI-green per condition.
* ``iteration_efficiency.png`` — distribution of pushes-to-green per condition.

This module imports ``matplotlib`` lazily so the rest of the harness (and the
core repo!) doesn't take a matplotlib dependency. Install the optional
``harness`` extra to get plotting deps: ``uv sync --extra harness``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "data" / "hackathon-runs" / "all.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "hackathon-runs"


# ---------------------------------------------------------------------------
# Loading & condition labelling.
# ---------------------------------------------------------------------------


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def condition_label(row: dict[str, Any]) -> str:
    """Stable per-condition string. Sorted-by-key so it's reproducible."""
    factors: dict[str, Any] = row.get("factors") or {}
    parts = [f"{k}={factors[k]}" for k in sorted(factors)]
    return " | ".join(parts) if parts else "(no factors)"


def group_by_condition(rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[condition_label(row)].append(row)
    return dict(sorted(out.items()))


# ---------------------------------------------------------------------------
# Metric computations (kept pure & matplotlib-free so they're easy to test).
# ---------------------------------------------------------------------------


def diversity_collapse_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Return {'top1': frac in modal layer, 'top3': frac in top-3 layers, 'n': N}."""
    layers = [row.get("layer_picked") for row in rows if row.get("layer_picked")]
    if not layers:
        return {"top1": 0.0, "top3": 0.0, "n": 0.0}
    counts = Counter(layers)
    ordered = counts.most_common()
    n = float(sum(counts.values()))
    top1 = ordered[0][1] / n
    top3 = sum(c for _, c in ordered[:3]) / n
    return {"top1": top1, "top3": top3, "n": n}


def calibration_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Return claimed-green vs actual-green fractions for one condition."""
    if not rows:
        return {"claimed": 0.0, "actual": 0.0, "n": 0.0, "gap": 0.0}
    claimed = sum(1 for r in rows if r.get("claimed_ci_green"))
    actual = sum(1 for r in rows if r.get("first_push_ci_green") is True)
    n = float(len(rows))
    return {
        "claimed": claimed / n,
        "actual": actual / n,
        "n": n,
        "gap": (claimed - actual) / n,
    }


def iteration_distribution(rows: list[dict[str, Any]]) -> list[int]:
    return [int(r["iterations_to_green"]) for r in rows if r.get("iterations_to_green") is not None]


# ---------------------------------------------------------------------------
# Plot routines (matplotlib imported lazily).
# ---------------------------------------------------------------------------


def _import_matplotlib() -> Any:
    try:
        import matplotlib  # type: ignore[import-not-found]

        matplotlib.use("Agg")  # pyright: ignore[reportUnknownMemberType]
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("matplotlib is not installed. Run `uv sync --extra harness`.") from exc
    return plt


def plot_diversity(grouped: dict[str, list[dict[str, Any]]], out: Path) -> None:
    plt = _import_matplotlib()
    labels = list(grouped.keys())
    metrics = [diversity_collapse_metrics(rows) for rows in grouped.values()]
    x = list(range(len(labels)))
    top1 = [m["top1"] for m in metrics]
    top3 = [m["top3"] for m in metrics]

    fig, ax = plt.subplots(figsize=(max(6.0, 1.6 * len(labels)), 4.5))
    width = 0.35
    ax.bar([i - width / 2 for i in x], top1, width=width, label="top-1 cluster share")
    ax.bar([i + width / 2 for i in x], top3, width=width, label="top-3 cluster share")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("share of submissions")
    ax.set_ylim(0, 1.05)
    ax.set_title("Diversity collapse: clustering of picked layers per condition")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def plot_calibration(grouped: dict[str, list[dict[str, Any]]], out: Path) -> None:
    plt = _import_matplotlib()
    labels = list(grouped.keys())
    metrics = [calibration_metrics(rows) for rows in grouped.values()]
    x = list(range(len(labels)))
    claimed = [m["claimed"] for m in metrics]
    actual = [m["actual"] for m in metrics]

    fig, ax = plt.subplots(figsize=(max(6.0, 1.6 * len(labels)), 4.5))
    width = 0.35
    ax.bar([i - width / 2 for i in x], claimed, width=width, label="claimed CI green")
    ax.bar([i + width / 2 for i in x], actual, width=width, label="actual CI green")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("fraction of submissions")
    ax.set_ylim(0, 1.05)
    ax.set_title("Calibration: claimed-pass vs actual-pass on first push")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def plot_iterations(grouped: dict[str, list[dict[str, Any]]], out: Path) -> None:
    plt = _import_matplotlib()
    labels = list(grouped.keys())
    distributions = [iteration_distribution(rows) for rows in grouped.values()]

    fig, ax = plt.subplots(figsize=(max(6.0, 1.6 * len(labels)), 4.5))
    # Boxplot is fine even when a condition has 0 data — fall back to empty arr.
    nonempty = [d if d else [0] for d in distributions]
    ax.boxplot(nonempty, tick_labels=labels)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("pushes until green CI")
    ax.set_title("Iteration efficiency: pushes-to-green per condition")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plot harness metrics.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    if not args.input.exists():
        sys.stderr.write(f"no input dataset at {args.input}\n")
        return 1

    rows = load_rows(args.input)
    if not rows:
        sys.stderr.write(f"{args.input} is empty\n")
        return 1
    grouped = group_by_condition(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    plot_diversity(grouped, args.output_dir / "diversity_collapse.png")
    plot_calibration(grouped, args.output_dir / "calibration.png")
    plot_iterations(grouped, args.output_dir / "iteration_efficiency.png")
    sys.stdout.write(f"wrote 3 plots to {args.output_dir}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
