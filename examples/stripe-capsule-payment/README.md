# Example: Stripe payment → sealed Agent Action Capsule

Wrap the NANDA `Payments` layer so every completed payment is sealed in
an [Agent Action Capsule][]. The capsule records the Stripe `payment_intent_id`,
amount, currency, and outcome — independently verifiable by any third
party without replaying the transaction.

## The pattern

```python
# SPDX-License-Identifier: Apache-2.0
import stripe
import capsule_emit
from nest_core.types import AgentId

class StripeCapsuledPayments:
    """NANDA Payments plugin: Stripe + capsule-emit."""

    async def pay(
        self,
        payer: AgentId,
        payee: AgentId,
        amount: float,
        currency: str = "usd",
        **metadata,
    ) -> dict:
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),          # Stripe uses cents
            currency=currency,
            confirm=True,
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        )
        # Seal the outcome — agent_input_digest commits to amount + intent id
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
            agent_output={
                "payment_intent_id": intent.id,
                "status": intent.status,
                "amount_received": intent.amount_received / 100,
            },
            verdict="executed",
            effect={"type": "stripe_payment", "status": intent.status},
        )
        return {"payment_intent_id": intent.id, "status": intent.status}

    async def verify_payment(self, payment_ref: dict) -> bool:
        intent = stripe.PaymentIntent.retrieve(payment_ref["payment_intent_id"])
        return intent.status == "succeeded"
```

## Register as a NANDA plugin

```toml
# pyproject.toml
[project.entry-points."nest.plugins.payments"]
stripe_capsule = "my_pkg.stripe_capsule:StripeCapsuledPayments"

[project.optional-dependencies]
nanda = ["capsule-emit", "stripe>=7.0"]
```

```bash
pip install -e .[nanda]
STRIPE_SECRET_KEY=sk_test_... nest run ./scenarios/marketplace.yaml  # layers.payments: stripe_capsule
```

## What the capsule proves

After any run, `capsule_ledger.jsonl` contains one entry per payment:

```bash
agent-action-capsule verify --store capsule_ledger.jsonl
```

Each capsule's `agent_input_digest` commits to the exact amount and
payer/payee pair at the moment the Stripe call was made. If a client
later disputes the amount, re-derive the digest from the disputed values
and compare to the sealed digest — a mismatch is proof the amount was
altered post-payment.

## Running offline (mock Stripe)

To run without real credentials, pass a mock client:

```python
import capsule_emit, unittest.mock

mock_stripe = unittest.mock.MagicMock()
mock_stripe.PaymentIntent.create.return_value = unittest.mock.MagicMock(
    id="pi_mock_abc123", status="succeeded", amount_received=2500
)

plugin = StripeCapsuledPayments(stripe_client=mock_stripe)
```

The capsule is still sealed and verifiable regardless of whether the
underlying Stripe call is real or mocked.

## Reference

- `capsule-emit` repo: <https://github.com/action-state-group/capsule-emit>
- Payments layer interface: [`docs/layers/payments.md`](../../docs/layers/payments.md)
- Reference payments plugin: [`prepaid_credits.py`](../../packages/nest-plugins-reference/nest_plugins_reference/payments/prepaid_credits.py)
- Plugin walkthrough: [`docs/writing-a-plugin.md`](../../docs/writing-a-plugin.md)

[Agent Action Capsule]: https://datatracker.ietf.org/doc/draft-steele-agent-action-capsule/
