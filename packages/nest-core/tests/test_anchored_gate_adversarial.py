# SPDX-License-Identifier: Apache-2.0
"""Adversarial acceptance tests for ``validate_receipt_reputation_anchored``.

The validator grades the anchoring property exclusively from deterministic trace
events — ``receipt:`` lines and ``seal:`` lines — with zero filesystem or
environment reads. These seven cases prove it in both directions.

Case 1: Honest capsule run -> PASS
Case 2: Non-anchoring baseline (no seal events) -> FAIL
Case 3: Stray ledger file on disk with no seals -> FAIL (file must not be read)
Case 4: Archived trace from different cwd with no ledger -> PASS (seals present)
Case 5: Stale ledger in cwd, no seal events -> FAIL
Case 6: Post-seal tamper (mutate receipt content) -> FAIL
Case 7: Chain tamper (reorder/drop seal event) -> FAIL
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from nest_core.canonical import SEAL_CHAIN_GENESIS, jcs_digest, seal_chain
from nest_core.validators import validate_receipt_reputation_anchored
from nest_plugins_reference.trust.agent_receipts import (
    cosign_receipt,
    did_for_pubkey,
    sign_receipt,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed(label: str) -> bytes:
    return hashlib.sha256(label.encode()).digest()[:32]


def _did(label: str) -> str:
    pub = (
        Ed25519PrivateKey.from_private_bytes(_seed(label))
        .public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    return did_for_pubkey(pub)


def _corroborated_receipt(issuer_label: str, cp_label: str, rid: str) -> dict[str, Any]:
    r: dict[str, Any] = {
        "receipt_id": rid,
        "issuer_did": _did(issuer_label),
        "action": {"category": "purchase", "counterparty_did": _did(cp_label)},
    }
    r = sign_receipt(r, issuer_seed=_seed(issuer_label))
    return cosign_receipt(r, counterparty_seed=_seed(cp_label))


def _receipt_event(receipt: dict[str, Any], agent: str = "honest-0") -> dict[str, Any]:
    return {"agent": agent, "kind": "send", "msg": "receipt:" + json.dumps(receipt), "ts": 0.0}


def _seal_events_from(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the seal:* broadcast lines exactly as CapsuleEmitTrust would emit them."""
    chain = SEAL_CHAIN_GENESIS
    events: list[dict[str, Any]] = []
    for seq, r in enumerate(receipts):
        digest = jcs_digest(r)
        chain = seal_chain(chain, digest)
        events.append(
            {
                "agent": "auditor-0",
                "kind": "broadcast",
                "msg": f"seal:{seq}:{digest}:{chain}",
                "ts": 1.0,
            }
        )
    return events


def _score_event() -> dict[str, Any]:
    return {
        "agent": "auditor-0",
        "kind": "broadcast",
        "msg": "score:honest-0:0.632121:1.000000:honest",
        "ts": 1.0,
    }


def _build_trace(receipts: list[dict[str, Any]], with_seals: bool = True) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [_receipt_event(r) for r in receipts]
    events.append(_score_event())
    if with_seals:
        events.extend(_seal_events_from(receipts))
    return events


def _anchored(events: list[dict[str, Any]]) -> Any:
    results = validate_receipt_reputation_anchored(events)
    matched = [r for r in results if r.name == "receipt_reputation_anchored"]
    assert matched, "receipt_reputation_anchored validator returned no result"
    return matched[0]


def _build_receipts() -> list[dict[str, Any]]:
    return [
        _corroborated_receipt("issuer-a", "cp-a", "r0"),
        _corroborated_receipt("issuer-b", "cp-b", "r1"),
        _corroborated_receipt("issuer-c", "cp-c", "r2"),
    ]


# ---------------------------------------------------------------------------
# A minimal "stale" capsule ledger fixture (old format, on-disk)
# ---------------------------------------------------------------------------


def _write_stale_ledger(path: Path, receipts: list[dict[str, Any]]) -> None:
    """Write a capsule_ledger.jsonl file in the old on-disk format."""
    with path.open("w") as f:
        for r in receipts:
            capsule = {
                "capsule_id": r.get("receipt_id", "?"),
                "model_attestation": {
                    "compute_attestation": {"agent_input_digest": jcs_digest(r)},
                },
            }
            f.write(json.dumps(capsule) + "\n")


# ---------------------------------------------------------------------------
# Case 1: Honest run -> PASS
# ---------------------------------------------------------------------------


def test_case1_honest_run_passes() -> None:
    """An honest capsule run with valid seals on the trace -> PASS."""
    receipts = _build_receipts()
    events = _build_trace(receipts, with_seals=True)
    result = _anchored(events)
    assert result.passed, f"Case 1 expected PASS: {result.detail}"
    assert "anchored" in result.detail


# ---------------------------------------------------------------------------
# Case 2: Non-anchoring baseline (no seal events) -> FAIL
# ---------------------------------------------------------------------------


def test_case2_no_seals_fails() -> None:
    """No ``seal:`` events on the trace -> FAIL (non-anchoring baseline)."""
    receipts = _build_receipts()
    events = _build_trace(receipts, with_seals=False)
    result = _anchored(events)
    assert not result.passed, "Case 2 expected FAIL"
    assert "does not anchor" in result.detail or "no capsule seals" in result.detail


# ---------------------------------------------------------------------------
# Case 3: Stray ledger file on disk, no seal events -> FAIL
# ---------------------------------------------------------------------------


def test_case3_stray_ledger_on_disk_no_seals_fails(tmp_path: Path) -> None:
    """A capsule_ledger.jsonl file on disk must NOT be read; without seals -> FAIL.

    The validator is event-only. Even if a stray ledger is present in the cwd,
    the absence of ``seal:`` trace events causes FAIL, proving no filesystem read.
    """
    receipts = _build_receipts()
    # Write a valid stale ledger to tmp_path and chdir there.
    ledger = tmp_path / "capsule_ledger.jsonl"
    _write_stale_ledger(ledger, receipts)

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        events = _build_trace(receipts, with_seals=False)  # NO seal events
        result = _anchored(events)
    finally:
        os.chdir(old_cwd)

    assert not result.passed, (
        "Case 3 expected FAIL: stray ledger on disk must not rescue a trace with no seals"
    )
    assert "does not anchor" in result.detail or "no capsule seals" in result.detail


# ---------------------------------------------------------------------------
# Case 4: Archived trace from different cwd, no ledger -> PASS (seals present)
# ---------------------------------------------------------------------------


def test_case4_archived_trace_different_cwd_passes(tmp_path: Path) -> None:
    """Trace with valid seal events from a cwd that has no ledger -> PASS.

    Proves the validator never falls back to reading a ledger from any cwd:
    the seals on the trace are the sole evidence, and they suffice.
    """
    receipts = _build_receipts()
    events = _build_trace(receipts, with_seals=True)  # seals present

    # cwd has no capsule_ledger.jsonl
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = _anchored(events)
    finally:
        os.chdir(old_cwd)

    assert result.passed, f"Case 4 expected PASS: {result.detail}"


# ---------------------------------------------------------------------------
# Case 5: Stale ledger in cwd, no seal events -> FAIL
# ---------------------------------------------------------------------------


def test_case5_stale_ledger_in_cwd_no_seals_fails(tmp_path: Path) -> None:
    """Stale ledger present in cwd, but no seal events on the trace -> FAIL.

    This is the same scenario as Case 3 restated: the stale file must be ignored.
    The validator uses only trace events, so no ledger file (regardless of
    content or location) can cause a PASS without matching seal events.
    """
    receipts = _build_receipts()
    stale_ledger = tmp_path / "capsule_ledger.jsonl"
    _write_stale_ledger(stale_ledger, receipts)

    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Trace has receipts but NO seal events.
        events = [_receipt_event(r) for r in receipts]
        events.append(_score_event())
        result = _anchored(events)
    finally:
        os.chdir(old_cwd)

    assert not result.passed, "Case 5 expected FAIL: stale ledger must not rescue missing seals"


# ---------------------------------------------------------------------------
# Case 6: Post-seal tamper (mutate receipt content) -> FAIL
# ---------------------------------------------------------------------------


def test_case6_post_seal_tamper_fails() -> None:
    """A receipt mutated after sealing no longer matches its sealed digest -> FAIL.

    The trace carries the original seal events (based on pre-mutation content)
    but the receipt lines carry the mutated content. The re-signed tampered
    receipt has a valid Ed25519 signature, so the validator accepts it into the
    receipt set — but its JCS digest does not match any sealed subject_digest.
    """
    receipts = _build_receipts()
    # Build seal events from the *original* receipts.
    seal_evs = _seal_events_from(receipts)

    # Re-build receipt[0] with a mutated category, freshly signed.
    tampered: dict[str, Any] = {
        "receipt_id": "r0",
        "issuer_did": _did("issuer-a"),
        "action": {"category": "premium_purchase", "counterparty_did": _did("cp-a")},
    }
    tampered = sign_receipt(tampered, issuer_seed=_seed("issuer-a"))
    tampered = cosign_receipt(tampered, counterparty_seed=_seed("cp-a"))

    tampered_receipts = [tampered, receipts[1], receipts[2]]
    events = [_receipt_event(r) for r in tampered_receipts]
    events.append(_score_event())
    events.extend(seal_evs)  # seals computed against original receipts

    result = _anchored(events)
    assert not result.passed, "Case 6 expected FAIL: tampered receipt must not be anchored"
    assert "not anchored" in result.detail or "not anchor" in result.detail


# ---------------------------------------------------------------------------
# Case 7: Chain tamper (reorder/drop seal event) -> FAIL
# ---------------------------------------------------------------------------


def test_case7_chain_tamper_fails() -> None:
    """Reordering or dropping a seal event breaks the chain replay -> FAIL."""
    receipts = _build_receipts()
    seal_evs = _seal_events_from(receipts)

    # Drop the first seal event (simulates a dropped/reordered seal).
    tampered_seals = seal_evs[1:]  # drop seq=0

    events = [_receipt_event(r) for r in receipts]
    events.append(_score_event())
    events.extend(tampered_seals)

    result = _anchored(events)
    assert not result.passed, "Case 7 expected FAIL: chain tamper must be detected"
    # Either the chain check fires or the completeness check fires.
    assert not result.passed
