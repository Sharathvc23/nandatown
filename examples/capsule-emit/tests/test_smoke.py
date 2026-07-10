# SPDX-License-Identifier: Apache-2.0
"""Smoke tests: instantiate both plugins and exercise one happy path each."""

import json

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
) -> dict:
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
    receipt: dict = {
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
async def test_trust_report_and_score(tmp_path: pytest.TempdirFactory) -> None:
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
async def test_sandbox_pay(tmp_path: pytest.TempdirFactory) -> None:
    plugin = StripeCapsuledPayments(ledger=str(tmp_path / "ledger.jsonl"))
    payer = AgentId("payer-1")
    payee = AgentId("payee-1")

    result = await plugin.pay(payer, payee, 19.99)
    assert result["status"] == "succeeded"
    assert result["payment_intent_id"].startswith("pi_sandbox_")
    assert result["amount_received"] == pytest.approx(19.99)


@pytest.mark.asyncio
async def test_sandbox_pay_is_deterministic(tmp_path: pytest.TempdirFactory) -> None:
    """Same inputs produce the same payment_intent_id (ledger is reproducible)."""
    plugin = StripeCapsuledPayments(ledger=str(tmp_path / "ledger.jsonl"), anchor=False)
    payer = AgentId("payer-x")
    payee = AgentId("payee-y")

    r1 = await plugin.pay(payer, payee, 50.00)
    r2 = await plugin.pay(payer, payee, 50.00)
    assert r1["payment_intent_id"] == r2["payment_intent_id"]


@pytest.mark.asyncio
async def test_gate3_tampered_receipt_excluded_from_score(tmp_path: pytest.TempdirFactory) -> None:
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
    plugin._receipts[-1]["action"]["category"] = "premium_purchase"

    # Gate 3 re-verification: verify_input_digest detects the mutation.
    # The capsule's sealed digest no longer matches → receipt excluded → score=0.
    score_after = await plugin.score(agent)
    assert score_after.score == 0.0, "Gate 3 must exclude tampered receipt from reputation"
    assert score_after.confidence == 0.0
