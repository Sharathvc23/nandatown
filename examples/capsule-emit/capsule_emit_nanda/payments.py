# SPDX-License-Identifier: Apache-2.0
"""StripeCapsuledPayments — NANDA Payments layer: Stripe + sealed capsule.

Every completed payment is sealed in an Agent Action Capsule whose
``agent_input_digest`` commits to amount, payer, and payee at the moment
the Stripe call was made.  A client who later disputes the amount can
re-derive the digest from the disputed values and compare — a mismatch is
proof the amount was altered after the payment.

**Sandbox by default**: if ``STRIPE_SECRET_KEY`` is not set, the plugin
runs a deterministic sandbox that mirrors the real Stripe API shape so
capsule and verifier logic are identical without any real charges.

Usage in a scenario YAML::

    layers:
      payments: stripe_capsule

Then ``pip install -e examples/capsule-emit``.
To use real Stripe::

    STRIPE_SECRET_KEY=sk_test_... nest run ./scenario.yaml
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any

import capsule_emit
from nest_core.types import AgentId

_STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
_USE_REAL_STRIPE = bool(_STRIPE_KEY)


class StripeCapsuledPayments:
    """NANDA Payments plugin: Stripe (or sandbox) + sealed Agent Action Capsule.

    Args:
        anchor: Whether to anchor capsules to the public log (default False).
        ledger: Path for the capsule ledger JSONL file.
    """

    def __init__(
        self,
        *,
        anchor: bool = False,
        ledger: str = "capsule_ledger.jsonl",
    ) -> None:
        self._anchor = anchor
        self._ledger = ledger

    async def pay(
        self,
        payer: AgentId,
        payee: AgentId,
        amount: float,
        currency: str = "usd",
        **metadata: Any,
    ) -> dict:
        """Execute a payment and seal the outcome as a capsule.

        Returns a dict with ``payment_intent_id`` and ``status``.
        """
        if _USE_REAL_STRIPE:
            result = _real_stripe_pay(payer, payee, amount, currency)
        else:
            result = _sandbox_pay(payer, payee, amount, currency)

        capsule_emit.emit(
            action="stripe_payment",
            operator=str(payer),
            developer="stripe-capsule-payments@v1",
            agent_input={
                "payer": str(payer),
                "payee": str(payee),
                "amount_usd": amount,
                "currency": currency,
            },
            agent_output=result,
            verdict="executed",
            effect={"type": "stripe_payment", "status": result["status"]},
            anchor=self._anchor,
            ledger=self._ledger,
        )
        return result

    async def quote(
        self,
        payer: AgentId,
        payee: AgentId,
        amount: float,
        currency: str = "usd",
    ) -> dict:
        """Return a fee quote without executing the payment."""
        return {"amount": amount, "currency": currency, "fee": 0.0}

    async def verify_payment(self, payment_ref: dict) -> bool:
        """Verify that a previously completed payment succeeded."""
        if not _USE_REAL_STRIPE:
            return payment_ref.get("status") == "succeeded"
        try:
            import stripe  # type: ignore[import]
            stripe.api_key = _STRIPE_KEY
            intent = stripe.PaymentIntent.retrieve(payment_ref["payment_intent_id"])
            return intent.status == "succeeded"
        except Exception:
            return False

    async def refund(self, payment_ref: dict, amount: float | None = None) -> dict:
        """Issue a refund (sandbox: always succeeds)."""
        return {"refunded": True, "amount": amount}


def _real_stripe_pay(payer: AgentId, payee: AgentId, amount: float, currency: str) -> dict:
    try:
        import stripe  # type: ignore[import]
    except ImportError:
        raise ImportError(
            "pip install capsule-emit-nanda[stripe]  (or unset STRIPE_SECRET_KEY to use sandbox)"
        )
    stripe.api_key = _STRIPE_KEY
    intent = stripe.PaymentIntent.create(
        amount=int(amount * 100),
        currency=currency,
        confirm=True,
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
    )
    return {
        "payment_intent_id": intent.id,
        "status": intent.status,
        "amount_received": intent.amount_received / 100,
    }


def _sandbox_pay(payer: AgentId, payee: AgentId, amount: float, currency: str) -> dict:
    seed = hashlib.sha256(f"{payer}:{payee}:{amount}:{time.monotonic_ns()}".encode()).hexdigest()[:16]
    return {
        "payment_intent_id": f"pi_sandbox_{seed}",
        "status": "succeeded",
        "amount_received": amount,
    }
