# SPDX-License-Identifier: Apache-2.0
"""CI-collected proof that the ``receipt_reputation_anchored`` trace validator grades
the CapsuleEmitTrust anchoring property.

The validator lives in ``nest_core.validators`` and is registered under
``VALIDATORS["receipt_reputation"]``, so the Nanda rig actually runs it via
``validate_trace``. These tests exercise it end-to-end against fixtures built the
same way the scenario builds receipts, proving:

* an anchored run (receipts sealed into a capsule ledger) PASSES;
* a non-anchoring baseline (no ledger produced) FAILS;
* a tampered run (a receipt mutated after sealing) FAILS.

The ledger fixtures are sealed with the *real* Agent Action Capsule digest
(``agent_action_capsule.canonical.json_digest``), while the validator recomputes
the digest with its own self-contained reimplementation -- so a passing test also
confirms the two agree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_action_capsule.canonical import json_digest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from nest_core.validators import validate_trace
from nest_plugins_reference.trust.agent_receipts import (
    cosign_receipt,
    did_for_pubkey,
    sign_receipt,
)

_SCENARIO = "receipt_reputation"


def _did(seed: bytes) -> str:
    pub = (
        Ed25519PrivateKey.from_private_bytes(seed)
        .public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    return did_for_pubkey(pub)


def _corroborated_receipt(issuer_seed: bytes, cp_seed: bytes, receipt_id: str) -> dict[str, Any]:
    """A valid, cross-signed receipt shaped exactly like the scenario's."""
    receipt: dict[str, Any] = {
        "receipt_id": receipt_id,
        "issuer_did": _did(issuer_seed),
        "action": {"category": "purchase", "counterparty_did": _did(cp_seed)},
    }
    signed = sign_receipt(receipt, issuer_seed=issuer_seed)
    return cosign_receipt(signed, counterparty_seed=cp_seed)


def _trace_events(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Trace lines the auditor/issuers emit: a ``receipt:`` per receipt plus a score line.

    Only the ``receipt:`` lines matter to the anchoring validator; the score line
    is included so the fixture resembles a real trace.
    """
    events: list[dict[str, Any]] = []
    for i, r in enumerate(receipts):
        events.append(
            {
                "agent": f"honest-{i}",
                "kind": "send",
                "msg": "receipt:" + json.dumps(r),
                "ts": 0.0,
            }
        )
    events.append(
        {
            "agent": "auditor-0",
            "kind": "broadcast",
            "msg": "score:honest-0:0.632121:1.000000:honest",
            "ts": 1.0,
        }
    )
    return events


def _write_trace(path: Path, events: list[dict[str, Any]]) -> None:
    with path.open("w") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")


def _seal_capsule(receipt: dict[str, Any]) -> dict[str, Any]:
    """A minimal ledger capsule sealing ``receipt`` under its real content digest."""
    return {
        "capsule_id": receipt["receipt_id"],
        "model_attestation": {
            "compute_attestation": {"agent_input_digest": json_digest(receipt)},
        },
    }


def _write_ledger(path: Path, receipts: list[dict[str, Any]]) -> None:
    with path.open("w") as f:
        for r in receipts:
            f.write(json.dumps(_seal_capsule(r)) + "\n")


def _anchored_result(trace: Path) -> Any:
    results = validate_trace(trace, _SCENARIO)
    anchored = [r for r in results if r.name == "receipt_reputation_anchored"]
    assert anchored, "receipt_reputation_anchored validator was not registered/run"
    return anchored[0]


def _build_receipts() -> list[dict[str, Any]]:
    seeds = [bytes([i]) * 32 for i in range(1, 5)]
    return [
        _corroborated_receipt(seeds[0], seeds[1], "honest-0->honest-1"),
        _corroborated_receipt(seeds[1], seeds[2], "honest-1->honest-2"),
        _corroborated_receipt(seeds[2], seeds[3], "honest-2->honest-3"),
    ]


def test_validator_passes_on_anchored_run(tmp_path: Path, monkeypatch: Any) -> None:
    """Every receipt sealed into the ledger -> anchoring holds -> PASS."""
    receipts = _build_receipts()
    trace = tmp_path / "trace.jsonl"
    ledger = tmp_path / "capsule_ledger.jsonl"
    _write_trace(trace, _trace_events(receipts))
    _write_ledger(ledger, receipts)

    monkeypatch.setenv("AAC_CAPSULE_LEDGER", str(ledger))
    result = _anchored_result(trace)
    assert result.passed, result.detail
    assert "anchored" in result.detail


def test_validator_fails_without_ledger(tmp_path: Path, monkeypatch: Any) -> None:
    """Non-anchoring baseline writes no ledger -> nothing anchored -> FAIL.

    This is the ``agent_receipts`` / ``score_average`` case: the same receipts on
    the wire, but no capsule ledger was ever produced.
    """
    receipts = _build_receipts()
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, _trace_events(receipts))

    # Point at a ledger path that does not exist -- the baseline produced none.
    monkeypatch.setenv("AAC_CAPSULE_LEDGER", str(tmp_path / "does_not_exist.jsonl"))
    result = _anchored_result(trace)
    assert not result.passed
    assert "no capsule ledger" in result.detail


def test_validator_fails_on_tampered_receipt(tmp_path: Path, monkeypatch: Any) -> None:
    """A receipt mutated after sealing no longer hashes to its sealed digest -> FAIL.

    The ledger is sealed against the original receipts; the trace then carries one
    receipt whose ``action.category`` was changed post-seal (the Gate-3 attack).
    The mutation is *re-signed* with the original issuer/counterparty keys, so the
    tampered receipt still carries a valid Ed25519 signature (the validator now
    verifies signatures, so a merely-stale signature would be discarded before the
    digest check) -- but its content digest no longer matches any sealed capsule.
    ``agent_receipts`` cannot detect this -- it has no ledger reference -- but the
    anchoring validator does.
    """
    receipts = _build_receipts()
    ledger = tmp_path / "capsule_ledger.jsonl"
    _write_ledger(ledger, receipts)  # sealed against the pristine receipts

    # Re-build receipt[0] with a mutated category, freshly signed with the same
    # keys _build_receipts used (issuer seeds[0], counterparty seeds[1]).
    seeds = [bytes([i]) * 32 for i in range(1, 5)]
    tampered0: dict[str, Any] = {
        "receipt_id": "honest-0->honest-1",
        "issuer_did": _did(seeds[0]),
        "action": {"category": "premium_purchase", "counterparty_did": _did(seeds[1])},
    }
    signed = sign_receipt(tampered0, issuer_seed=seeds[0])
    tampered0 = cosign_receipt(signed, counterparty_seed=seeds[1])

    tampered = [tampered0, receipts[1], receipts[2]]
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, _trace_events(tampered))

    monkeypatch.setenv("AAC_CAPSULE_LEDGER", str(ledger))
    result = _anchored_result(trace)
    assert not result.passed
    assert "not anchored" in result.detail


def test_validator_fails_when_no_receipts(tmp_path: Path, monkeypatch: Any) -> None:
    """A trace with no receipt lines cannot demonstrate anchoring -> FAIL (no tautology)."""
    trace = tmp_path / "trace.jsonl"
    _write_trace(trace, [{"agent": "auditor-0", "kind": "broadcast", "msg": "finalize:"}])
    ledger = tmp_path / "capsule_ledger.jsonl"
    _write_ledger(ledger, _build_receipts())

    monkeypatch.setenv("AAC_CAPSULE_LEDGER", str(ledger))
    result = _anchored_result(trace)
    assert not result.passed
    assert "no receipts" in result.detail


def test_validator_ignores_invalid_signature_receipt_line(tmp_path: Path, monkeypatch: Any) -> None:
    """An injected receipt line with a bad issuer signature is ignored -> still PASS (H1).

    A hostile reviewer can splice an extra ``receipt:`` line into the trace whose
    issuer signature does not verify. The trust plugin never anchors it (it fails
    Gate 1), so the validator must not demand it be anchored -- otherwise a
    faithful, fully-anchored run would FAIL. ``_collect_receipts`` verifies the
    Ed25519 issuer signature, so the forged line is dropped and the run PASSES.
    """
    receipts = _build_receipts()
    trace_events = _trace_events(receipts)

    # Splice in a forged receipt: valid shape, but the signature is garbage, so it
    # was never anchored by the plugin. It must not force the anchoring check to fail.
    forged: dict[str, Any] = {
        "receipt_id": "forged->victim",
        "issuer_did": _did(bytes([9]) * 32),
        "action": {"category": "purchase", "counterparty_did": _did(bytes([10]) * 32)},
        "signature": "00" * 64,  # not a valid signature over the issuer payload
    }
    trace_events.insert(
        1,
        {"agent": "attacker", "kind": "send", "msg": "receipt:" + json.dumps(forged), "ts": 0.5},
    )

    trace = tmp_path / "trace.jsonl"
    ledger = tmp_path / "capsule_ledger.jsonl"
    _write_trace(trace, trace_events)
    _write_ledger(ledger, receipts)  # only the genuine receipts are sealed

    monkeypatch.setenv("AAC_CAPSULE_LEDGER", str(ledger))
    result = _anchored_result(trace)
    assert result.passed, result.detail
    assert "anchored" in result.detail
