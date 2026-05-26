# SPDX-License-Identifier: Apache-2.0
"""Load and expand experimental conditions from `conditions.yaml`.

A *condition* is a YAML doc describing experiment factors (dimensions).
A *cell* is one fully-specified combination of factor levels, identified by a
stable `cell_id` so the same factor combo always maps to the same id, on any
machine, in any process.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

# Default path used by the CLI when none is provided.
DEFAULT_CONDITIONS_PATH = Path(__file__).parent / "conditions.yaml"


@dataclass(frozen=True)
class Cell:
    """One fully-specified experimental condition (a point in factor space)."""

    cell_id: str
    factors: dict[str, str]
    conditions_version: int
    defaults: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConditionsSpec:
    """Parsed `conditions.yaml`, ready to expand into cells."""

    conditions_version: int
    dimensions: dict[str, list[str]]
    defaults: dict[str, Any]
    skip: list[dict[str, str]]
    source_path: Path | None = None

    def cells(self) -> Iterator[Cell]:
        """Yield every (non-skipped) cell in deterministic factor order."""
        dim_names = sorted(self.dimensions.keys())
        levels = [self.dimensions[name] for name in dim_names]
        for combo in itertools.product(*levels):
            factors = dict(zip(dim_names, combo, strict=True))
            if _matches_any(factors, self.skip):
                continue
            yield Cell(
                cell_id=compute_cell_id(factors, self.conditions_version),
                factors=factors,
                conditions_version=self.conditions_version,
                defaults=dict(self.defaults),
            )

    def get_cell(self, cell_id: str) -> Cell | None:
        for cell in self.cells():
            if cell.cell_id == cell_id:
                return cell
        return None


def _matches_any(factors: dict[str, str], skip: list[dict[str, str]]) -> bool:
    return any(all(factors.get(k) == v for k, v in entry.items()) for entry in skip)


def compute_cell_id(factors: dict[str, str], conditions_version: int) -> str:
    """Stable 12-char sha256 hex prefix of canonicalised (factors, version).

    Stability: the JSON dump is sorted-keys + no whitespace, so equal factor
    dicts on any machine produce equal ids. The conditions_version is folded
    in so a bump invalidates old ids without renaming dimensions.
    """
    payload = json.dumps(
        {"v": conditions_version, "factors": factors},
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest[:12]


def load_conditions(path: Path | str | None = None) -> ConditionsSpec:
    """Read and validate a conditions YAML file."""
    resolved = Path(path) if path is not None else DEFAULT_CONDITIONS_PATH
    with resolved.open("r", encoding="utf-8") as fh:
        raw_obj: object = yaml.safe_load(fh)
    if not isinstance(raw_obj, dict):
        raise ValueError(f"{resolved}: top-level must be a mapping")
    raw = cast("dict[str, Any]", raw_obj)

    conditions_version = int(raw.get("conditions_version", 1))

    dims_obj: object = raw.get("dimensions") or {}
    if not isinstance(dims_obj, dict) or not dims_obj:
        raise ValueError(f"{resolved}: 'dimensions' must be a non-empty mapping")
    dims_raw = cast("dict[str, Any]", dims_obj)
    dimensions: dict[str, list[str]] = {}
    for name_obj, body_obj in dims_raw.items():
        name = str(cast("object", name_obj))
        if not isinstance(body_obj, dict) or "levels" not in body_obj:
            raise ValueError(f"{resolved}: dimension {name!r} must have a 'levels' list")
        body = cast("dict[str, Any]", body_obj)
        levels_obj: object = body["levels"]
        if not isinstance(levels_obj, list) or not levels_obj:
            raise ValueError(f"{resolved}: dimension {name!r} has empty 'levels'")
        levels = cast("list[Any]", levels_obj)
        dimensions[name] = [str(cast("object", lvl)) for lvl in levels]

    defaults_obj: object = raw.get("defaults") or {}
    if not isinstance(defaults_obj, dict):
        raise ValueError(f"{resolved}: 'defaults' must be a mapping if set")
    defaults_raw = cast("dict[str, Any]", defaults_obj)

    skip_obj: object = raw.get("skip") or []
    if not isinstance(skip_obj, list):
        raise ValueError(f"{resolved}: 'skip' must be a list if set")
    skip_raw = cast("list[Any]", skip_obj)
    skip: list[dict[str, str]] = []
    for entry_obj in skip_raw:
        if not isinstance(entry_obj, dict):
            raise ValueError(f"{resolved}: 'skip' entries must be mappings")
        entry = cast("dict[str, Any]", entry_obj)
        skip.append({str(cast("object", k)): str(cast("object", v)) for k, v in entry.items()})

    return ConditionsSpec(
        conditions_version=conditions_version,
        dimensions=dimensions,
        defaults={str(cast("object", k)): v for k, v in defaults_raw.items()},
        skip=skip,
        source_path=resolved,
    )


def list_cells(spec: ConditionsSpec) -> list[Cell]:
    return list(spec.cells())


__all__ = [
    "Cell",
    "ConditionsSpec",
    "DEFAULT_CONDITIONS_PATH",
    "compute_cell_id",
    "list_cells",
    "load_conditions",
]
