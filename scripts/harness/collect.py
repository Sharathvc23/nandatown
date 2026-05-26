# SPDX-License-Identifier: Apache-2.0
"""Aggregate per-cell JSONLs into one ``all.jsonl``.

Refuses to merge rows whose ``schema_version`` differs from the current one
so analyses don't silently drift. Sorts the output deterministically by
``(cell_id, run_idx)`` to make diffs across runs easy to read.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from scripts.harness import SCHEMA_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "data" / "hackathon-runs"


def discover_inputs(input_dir: Path) -> list[Path]:
    """Find per-cell JSONLs, ignoring the aggregated `all.jsonl`."""
    return sorted(p for p in input_dir.glob("*.jsonl") if p.name != "all.jsonl")


def load_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row_obj: object = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{lineno}: bad JSON: {exc}") from exc
                if not isinstance(row_obj, dict):
                    raise ValueError(f"{path}:{lineno}: row is not an object")
                row = cast("dict[str, Any]", row_obj)
                version = row.get("schema_version")
                if version != SCHEMA_VERSION:
                    raise ValueError(
                        f"{path}:{lineno}: schema_version={version!r} but harness "
                        f"is at {SCHEMA_VERSION}. Rerun the cell or bump the harness."
                    )
                rows.append(row)
    rows.sort(key=lambda r: (str(r.get("cell_id", "")), int(r.get("run_idx", 0))))
    return rows


def write_all(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate per-cell JSONLs.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSONL path (default: <input-dir>/all.jsonl).",
    )
    args = parser.parse_args(argv)

    output = args.output if args.output is not None else args.input_dir / "all.jsonl"
    inputs = discover_inputs(args.input_dir)
    if not inputs:
        sys.stderr.write(f"no per-cell JSONL files found in {args.input_dir}\n")
        return 1
    rows = load_rows(inputs)
    write_all(rows, output)
    sys.stdout.write(f"wrote {len(rows)} rows from {len(inputs)} cells to {output}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
