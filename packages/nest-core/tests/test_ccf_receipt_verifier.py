# SPDX-License-Identifier: Apache-2.0
"""Fail-closed unit tests for the vendored CCF write-receipt verifier.

``verify_ccf_write_receipt`` must return ``False`` — never raise, never
default open — for every malformed, truncated, mutated, or mis-keyed input,
and ``True`` only for a receipt whose inclusion proof, endorsement, and
service-identity signature all check out for the exact claim.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, cast

from nest_core.ccf_receipt import verify_ccf_write_receipt
from nest_mocks.ccf_ledger import (
    WRONG_SERVICE_LABEL,
    LocalTestConfidentialLedger,
    receipt_bytes,
)

_LEDGER = LocalTestConfidentialLedger()
_CLAIMS = [f"claim-{i}".encode() for i in range(5)]
_RECEIPTS = _LEDGER.write_receipts(_CLAIMS)
_PEM = _LEDGER.service_identity_pem


def _clone(receipt: dict[str, Any]) -> dict[str, Any]:
    return json.loads(receipt_bytes(receipt).decode("utf-8"))


def test_honest_receipts_verify_and_bind_their_claim() -> None:
    for wr, claim in zip(_RECEIPTS, _CLAIMS, strict=True):
        assert verify_ccf_write_receipt(wr, claim, _PEM)
    # Receipt for claim 0 must not verify claim 1 (binding).
    assert not verify_ccf_write_receipt(_RECEIPTS[0], _CLAIMS[1], _PEM)


def test_tree_shapes_from_one_to_nine_leaves() -> None:
    """Odd/even/promoted-leaf tree shapes all produce verifying proofs."""
    for n in range(1, 10):
        claims = [f"n{n}-c{i}".encode() for i in range(n)]
        receipts = _LEDGER.write_receipts(claims)
        for wr, claim in zip(receipts, claims, strict=True):
            assert verify_ccf_write_receipt(wr, claim, _PEM), f"n={n} claim={claim!r}"


def test_wrong_identity_rejected_both_directions() -> None:
    imposter = LocalTestConfidentialLedger(WRONG_SERVICE_LABEL)
    assert not verify_ccf_write_receipt(_RECEIPTS[0], _CLAIMS[0], imposter.service_identity_pem)
    forged = imposter.write_receipts(_CLAIMS)
    assert not verify_ccf_write_receipt(forged[0], _CLAIMS[0], _PEM)


def test_unendorsed_self_made_cert_rejected() -> None:
    """A receipt re-signed under a self-made node cert the identity never issued."""
    rogue = LocalTestConfidentialLedger(WRONG_SERVICE_LABEL)
    forged = rogue.write_receipts(_CLAIMS)[0]
    # Correct leaf components for the claim, but the cert chain dies at the
    # pinned identity: rogue's node cert is not issued by the pinned service.
    forged["leaf_components"] = _clone(_RECEIPTS[0])["leaf_components"]
    assert not verify_ccf_write_receipt(forged, _CLAIMS[0], _PEM)


def _set_field(receipt: dict[str, Any], key: str, value: Any) -> None:
    receipt[key] = value


def _drop_field(receipt: dict[str, Any], key: str) -> None:
    receipt.pop(key)


def _set_leaf(receipt: dict[str, Any], key: str, value: Any) -> None:
    cast("dict[str, Any]", receipt["leaf_components"])[key] = value


def _drop_leaf(receipt: dict[str, Any], key: str) -> None:
    cast("dict[str, Any]", receipt["leaf_components"]).pop(key)


def test_every_field_mutation_is_rejected() -> None:
    """Any single-field tamper on a valid receipt must fail verification."""
    wr, claim = _RECEIPTS[2], _CLAIMS[2]
    truncated_proof = cast("list[Any]", _clone(wr)["proof"])[:-1]

    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("garbage signature", lambda r: _set_field(r, "signature", "AAAA")),
        ("non-base64 signature", lambda r: _set_field(r, "signature", "not base64!")),
        ("null signature", lambda r: _set_field(r, "signature", None)),
        ("missing signature", lambda r: _drop_field(r, "signature")),
        ("garbage cert", lambda r: _set_field(r, "cert", "not a pem")),
        ("missing cert", lambda r: _drop_field(r, "cert")),
        ("empty proof", lambda r: _set_field(r, "proof", [])),
        ("truncated proof", lambda r: _set_field(r, "proof", truncated_proof)),
        ("non-hex proof step", lambda r: _set_field(r, "proof", [{"left": "zz"}])),
        ("unknown proof side", lambda r: _set_field(r, "proof", [{"up": "00" * 32}])),
        (
            "two-sided proof step",
            lambda r: _set_field(r, "proof", [{"left": "00" * 32, "right": "00" * 32}]),
        ),
        ("missing proof", lambda r: _drop_field(r, "proof")),
        ("claims digest swap", lambda r: _set_leaf(r, "claims_digest", "00" * 32)),
        ("write-set digest swap", lambda r: _set_leaf(r, "write_set_digest", "00" * 32)),
        ("commit evidence swap", lambda r: _set_leaf(r, "commit_evidence", "ce:tampered")),
        ("empty commit evidence", lambda r: _set_leaf(r, "commit_evidence", "")),
        ("missing claims digest", lambda r: _drop_leaf(r, "claims_digest")),
        ("missing leaf components", lambda r: _drop_field(r, "leaf_components")),
    ]
    for label, mutate in mutations:
        mutated = _clone(wr)
        mutate(mutated)
        assert not verify_ccf_write_receipt(mutated, claim, _PEM), f"survived: {label}"


def test_proof_step_swap_rejected() -> None:
    """Swapping a proof step's side (left<->right) must break the fold."""
    wr, claim = _RECEIPTS[0], _CLAIMS[0]
    mutated = _clone(wr)
    proof = cast("list[dict[str, str]]", mutated["proof"])
    assert proof, "expected a non-trivial proof for a 5-leaf tree"
    ((side, value),) = proof[0].items()
    proof[0] = {("right" if side == "left" else "left"): value}
    assert not verify_ccf_write_receipt(mutated, claim, _PEM)


def test_garbage_shapes_never_raise() -> None:
    garbage_shapes: list[dict[str, Any]] = [
        {},
        {"cert": 5, "leaf_components": [], "proof": "x", "signature": 9},
        {"leaf_components": {"claims_digest": hashlib.sha256(_CLAIMS[0]).hexdigest()}},
        {"cert": _PEM, "leaf_components": None, "proof": None, "signature": None},
    ]
    for garbage in garbage_shapes:
        assert not verify_ccf_write_receipt(garbage, _CLAIMS[0], _PEM)


def test_empty_batch_rejected_by_ledger() -> None:
    try:
        _LEDGER.write_receipts([])
    except ValueError:
        return
    raise AssertionError("empty batch must raise")
