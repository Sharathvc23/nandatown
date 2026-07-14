# SPDX-License-Identifier: Apache-2.0
"""End-to-end tests for the ``receipt_reputation_capsule`` scenario pipeline.

These run the real scenario (runner → auditor → trace → validators) with the
``capsule_emit`` trust plugin and prove the graded default state is honest and
fail-closed: until the operator-gated pre-anchor step commits real ledger
write-receipt fixtures and pins the production service identity, the anchored
check FAILS — while the reputation checks (ring severance, honest confidence)
already PASS and the trace stays byte-deterministic.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from nest_core.runner import ScenarioRunner
from nest_core.scenario import ScenarioConfig
from nest_core.validators import validate_trace

_SCENARIO_YAML = (
    Path(__file__).parent.parent.parent.parent / "scenarios" / "receipt_reputation_capsule.yaml"
)


def _config(trace: Path, seed: int | None = None) -> ScenarioConfig:
    config = ScenarioConfig.from_yaml(_SCENARIO_YAML)
    config.output.trace = str(trace)
    if seed is not None:
        config.seed = seed
    return config


@pytest.mark.asyncio
async def test_capsule_scenario_grades_fail_closed_without_fixtures(tmp_path: Path) -> None:
    """No committed fixtures + no pinned identity -> anchored FAILS, rest PASSES."""
    trace = tmp_path / "capsule.jsonl"
    await ScenarioRunner(_config(trace)).run()

    results = {r.name: r for r in validate_trace(trace, "receipt_reputation_capsule")}
    assert results["receipt_reputation_ring_severed"].passed
    assert results["receipt_reputation_honest_confidence"].passed
    anchored = results["receipt_reputation_anchored"]
    assert not anchored.passed, (
        "anchored must FAIL until real ledger receipts are committed and the "
        f"service identity is pinned; got: {anchored.detail}"
    )

    # The plugin seals (trip-wire lines present) but emits no anchoring
    # evidence — there are no committed write-receipt fixtures to replay.
    msgs = [json.loads(line).get("msg", "") for line in trace.read_text().splitlines()]
    assert any(str(m).startswith("seal:") for m in msgs)
    assert not any(str(m).startswith("ccfreceipt:") for m in msgs)


@pytest.mark.asyncio
async def test_capsule_scenario_trace_is_deterministic(tmp_path: Path) -> None:
    """Same seed -> byte-identical trace (the pre-anchor fixtures rely on this)."""
    t1, t2 = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    await ScenarioRunner(_config(t1, seed=42)).run()
    await ScenarioRunner(_config(t2, seed=42)).run()
    d1 = hashlib.sha256(t1.read_bytes()).hexdigest()
    d2 = hashlib.sha256(t2.read_bytes()).hexdigest()
    assert d1 == d2
