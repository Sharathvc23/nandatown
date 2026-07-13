# SPDX-License-Identifier: Apache-2.0
"""Smoke tests: instantiate both plugins and exercise one happy path each."""

import json
from pathlib import Path
from typing import Any

import pytest
from capsule_emit_nanda.payments import StripeCapsuledPayments
from capsule_emit_nanda.trust import CapsuleEmitTrust
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from nest_core.types import AgentId, Evidence
from nest_plugins_reference.trust.agent_receipts import (
    cosign_receipt,
    did_for_pubkey,
    sign_receipt,
)


@pytest.fixture(autouse=True)
def no_real_stripe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure sandbox mode regardless of the host environment."""
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)


def _make_corroborated_receipt(
    issuer_seed: bytes, counterparty_seed: bytes, action_id: str = "act-1"
) -> dict[str, Any]:
    """Return a signed and co-signed receipt using the two given seeds.

    ``counterparty_did`` lives inside ``action`` (where _counterparty() reads it)
    and the co-signature rides in ``evidence.witness_signatures`` (where
    is_corroborated() checks it).
    """
    issuer_pub = (
        Ed25519PrivateKey.from_private_bytes(issuer_seed)
        .public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    cp_pub = (
        Ed25519PrivateKey.from_private_bytes(counterparty_seed)
        .public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    receipt: dict[str, Any] = {
        "issuer_did": did_for_pubkey(issuer_pub),
        "action": {
            "category": "purchase",
            "action_id": action_id,
            "counterparty_did": did_for_pubkey(cp_pub),
        },
    }
    signed = sign_receipt(receipt, issuer_seed=issuer_seed)
    return cosign_receipt(signed, counterparty_seed=counterparty_seed)


@pytest.mark.asyncio
async def test_trust_report_and_score(tmp_path: Path) -> None:
    plugin = CapsuleEmitTrust(ledger=tmp_path / "ledger.jsonl")
    agent = AgentId("agent-a")
    reporter = AgentId("agent-b")

    # Plain-string evidence triggers the fallback reputation path.
    ev = Evidence(reporter=reporter, subject=agent, kind="positive", detail="good work")
    await plugin.report(agent, ev)

    score = await plugin.score(agent)
    assert score.agent_id == agent
    assert 0.0 <= score.score <= 1.0


@pytest.mark.asyncio
async def test_sandbox_pay(tmp_path: Path) -> None:
    plugin = StripeCapsuledPayments(ledger=str(tmp_path / "ledger.jsonl"))
    payer = AgentId("payer-1")
    payee = AgentId("payee-1")

    result = await plugin.pay(payer, payee, 19.99)
    assert result["status"] == "succeeded"
    assert result["payment_intent_id"].startswith("pi_sandbox_")
    assert result["amount_received"] == pytest.approx(19.99)


@pytest.mark.asyncio
async def test_sandbox_pay_is_deterministic(tmp_path: Path) -> None:
    """Same inputs produce the same payment_intent_id (ledger is reproducible)."""
    plugin = StripeCapsuledPayments(ledger=str(tmp_path / "ledger.jsonl"), anchor=False)
    payer = AgentId("payer-x")
    payee = AgentId("payee-y")

    r1 = await plugin.pay(payer, payee, 50.00)
    r2 = await plugin.pay(payer, payee, 50.00)
    assert r1["payment_intent_id"] == r2["payment_intent_id"]


@pytest.mark.asyncio
async def test_gate3_tampered_receipt_excluded_from_score(tmp_path: Path) -> None:
    """Gate 3 fires: agent_receipts accepts a mutated record; CapsuleEmitTrust rejects it.

    Attack: an adversary modifies a receipt's action category in-memory after the
    capsule is sealed.  agent_receipts re-scores whatever is in its receipt list
    (no ledger reference), so it would assign full reputation.  CapsuleEmitTrust
    calls verify_input_digest() at score time — the sealed digest no longer matches
    the mutated receipt, so the receipt is excluded and the score drops to zero.
    """
    import hashlib

    # Seeds derived the same way CapsuleEmitTrust._did_of() does — ensures the
    # receipt's issuer_did matches what score() looks up for AgentId("honest-agent").
    issuer_seed = hashlib.sha256(b"honest-agent").digest()[:32]
    cp_seed = hashlib.sha256(b"counterparty").digest()[:32]

    plugin = CapsuleEmitTrust(anchor=False, ledger=tmp_path / "ledger.jsonl")
    receipt = _make_corroborated_receipt(issuer_seed, cp_seed)
    agent = AgentId("honest-agent")

    ev = Evidence(
        reporter=AgentId("counterparty"),
        subject=agent,
        kind="positive",
        detail=json.dumps(receipt),
    )
    await plugin.report(agent, ev)

    # Before tampering: valid, anchored receipt contributes to score.
    score_before = await plugin.score(agent)
    assert score_before.score > 0.0, "valid corroborated receipt should build reputation"
    assert score_before.confidence > 0.0

    # Adversary mutates the in-memory receipt (agent_receipts has no defence here).
    plugin.receipts[-1]["action"]["category"] = "premium_purchase"

    # Gate 3 re-verification: verify_input_digest detects the mutation.
    # The capsule's sealed digest no longer matches → receipt excluded → score=0.
    score_after = await plugin.score(agent)
    assert score_after.score == 0.0, "Gate 3 must exclude tampered receipt from reputation"
    assert score_after.confidence == 0.0


@pytest.mark.asyncio
async def test_float_bearing_receipt_does_not_crash_score(tmp_path: Path) -> None:
    """B2: a receipt carrying a raw float must never crash score().

    ``json_digest`` raises ``FloatInDigestError`` (a ``ValueError``) on a raw
    float. Two independent guards keep that raise from taking down the run:

    * ``_emit_capsule`` narrows its ``except`` so a float that breaks ``emit()``
      is counted and skipped (the receipt is simply not anchored); and
    * ``_verify_anchored`` wraps the Gate-3 ``verify_input_digest`` call so a
      raise there is treated as "not verified" and excluded.

    Either way, reporting a valid, corroborated, *float-bearing* receipt and then
    scoring the agent must return cleanly rather than propagate the exception.
    """
    import hashlib

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from nest_plugins_reference.trust.agent_receipts import (
        cosign_receipt,
        did_for_pubkey,
        sign_receipt,
    )

    issuer_seed = hashlib.sha256(b"floaty-agent").digest()[:32]
    cp_seed = hashlib.sha256(b"floaty-cp").digest()[:32]
    issuer_pub = (
        Ed25519PrivateKey.from_private_bytes(issuer_seed)
        .public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    cp_pub = (
        Ed25519PrivateKey.from_private_bytes(cp_seed)
        .public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    # A valid, corroborated receipt that carries a raw float in its action.
    receipt: dict[str, Any] = {
        "issuer_did": did_for_pubkey(issuer_pub),
        "action": {
            "category": "purchase",
            "amount": 19.99,  # raw float -> FloatInDigestError in the digest path
            "counterparty_did": did_for_pubkey(cp_pub),
        },
    }
    receipt = sign_receipt(receipt, issuer_seed=issuer_seed)
    receipt = cosign_receipt(receipt, counterparty_seed=cp_seed)

    plugin = CapsuleEmitTrust(anchor=False, ledger=tmp_path / "ledger.jsonl")
    agent = AgentId("floaty-agent")
    ev = Evidence(
        reporter=AgentId("floaty-cp"),
        subject=agent,
        kind="positive",
        detail=json.dumps(receipt),
    )
    await plugin.report(agent, ev)  # must not raise despite the float

    # Must NOT raise; the float-bearing receipt cannot be digest-verified so it is
    # excluded, and score() returns cleanly.
    score = await plugin.score(agent)
    assert 0.0 <= score.score <= 1.0
    assert score.score == 0.0, "a receipt that cannot be digest-verified must not build reputation"


@pytest.mark.asyncio
async def test_multiple_receipts_same_pair_same_category_all_anchored(tmp_path: Path) -> None:
    """H2: several receipts between the same pair in the same category all count.

    ``_anchored`` is keyed by each receipt's content digest, so repeated
    same-issuer/same-counterparty/same-category receipts no longer overwrite one
    another and drop from Gate 3. With three such receipts, Gate-3 confidence must
    be 1.0 (all three anchored) — not 1/3 as it would be under the old
    ``(issuer, counterparty, category)`` key.
    """
    import hashlib

    issuer_seed = hashlib.sha256(b"repeat-agent").digest()[:32]
    cp_seed = hashlib.sha256(b"repeat-cp").digest()[:32]
    agent = AgentId("repeat-agent")

    plugin = CapsuleEmitTrust(anchor=False, ledger=tmp_path / "ledger.jsonl")

    # Three distinct receipts, same pair, same category ("purchase"), no action_id
    # (mirrors the scenario's receipts) — distinguished only by a per-receipt nonce.
    for n in range(3):
        receipt = _make_corroborated_receipt(issuer_seed, cp_seed, action_id=f"nonce-{n}")
        # Drop action_id so the pair+category are identical across all three; keep a
        # distinguishing field so each receipt's content digest still differs.
        del receipt["action"]["action_id"]
        receipt["action"]["nonce"] = n
        # Re-sign after editing so the signature covers the final content.
        from nest_plugins_reference.trust.agent_receipts import (
            cosign_receipt,
            sign_receipt,
        )

        base = {k: v for k, v in receipt.items() if k not in ("signature", "evidence")}
        signed = sign_receipt(base, issuer_seed=issuer_seed)
        receipt = cosign_receipt(signed, counterparty_seed=cp_seed)

        ev = Evidence(
            reporter=AgentId("repeat-cp"),
            subject=agent,
            kind="positive",
            detail=json.dumps(receipt),
        )
        await plugin.report(agent, ev)

    assert len(plugin.receipts) == 3
    score = await plugin.score(agent)
    assert score.sample_count == 3
    # All three are anchored and survive Gate 3 -> full confidence.
    assert score.confidence == pytest.approx(1.0), (
        "all same-pair/same-category receipts must remain anchored (no key collision)"
    )
    assert score.score > 0.0
