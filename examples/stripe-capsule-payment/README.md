# Payments demo: `stripe_capsule`

> **Demo** — `StripeCapsuledPayments` is a standalone demo, not a
> conforming NANDA Payments protocol implementation.  The protocol requires
> `pay(to, amount, ref) -> Receipt`; this plugin uses a different signature
> and its `quote`/`verify_payment`/`refund` methods diverge from the
> protocol contract.  `@runtime_checkable` only checks method *names*, so
> an `isinstance` check will falsely pass.
>
> **Payee caveat (real-Stripe path):** the PaymentIntent is created without
> a `destination` or `transfer_data` parameter, so `payee` is **not
> enforced at the Stripe level** — the capsule commits to the payer/payee
> pair by digest, but the charge does not route to the payee.

Wrap a Stripe call so every completed payment is sealed in an
[Agent Action Capsule][]. The capsule records the Stripe `payment_intent_id`,
amount, currency, and outcome — independently verifiable by any third party
without replaying the transaction.

**Sandbox by default** — no `STRIPE_SECRET_KEY` required, no real charges.

## Install

```bash
pip install -e examples/capsule-emit         # sandbox (no Stripe key needed)
pip install -e "examples/capsule-emit[stripe]"   # real Stripe payments
```

## Use in any scenario YAML

```yaml
layers:
  payments: stripe_capsule
```

```bash
# Sandbox (default, no key needed):
nest run ./scenario.yaml

# Real Stripe:
STRIPE_SECRET_KEY=sk_test_... nest run ./scenario.yaml
```

## What the capsule proves

After any run, `capsule_ledger.jsonl` contains one entry per payment:

```bash
agent-action-capsule verify --store capsule_ledger.jsonl
```

Each capsule's `agent_input_digest` commits to the exact amount and
payer/payee pair at the moment the Stripe call was made. If a client
later disputes the amount, re-derive the digest from the disputed values
and compare — a mismatch is proof the amount was altered post-payment.

## The pattern

```python
# SPDX-License-Identifier: Apache-2.0
# From capsule_emit_nanda/payments.py

import capsule_emit
from nest_core.types import AgentId

class StripeCapsuledPayments:
    async def pay(self, payer: AgentId, payee: AgentId, amount: float,
                  currency: str = "usd", **metadata) -> dict:
        # Execute Stripe payment (or sandbox)
        result = _stripe_pay(payer, payee, amount, currency)

        # Seal the outcome — agent_input_digest commits to amount + intent id
        capsule_emit.emit(
            action="stripe_payment",
            operator=str(payer),
            developer="stripe-capsule-payments@v1",
            agent_input={"payer": str(payer), "payee": str(payee),
                         "amount_usd": amount, "currency": currency},
            agent_output=result,
            verdict="executed",
            effect={"type": "stripe_payment", "status": result["status"]},
        )
        return result
```

## Reference

- Plugin package: [`examples/capsule-emit/`](../capsule-emit/)
- `capsule-emit` repo: <https://github.com/action-state-group/capsule-emit>
- Payments layer interface: [`docs/layers/payments.md`](../../docs/layers/payments.md)
- Reference payments plugin: [`prepaid_credits.py`](../../packages/nest-plugins-reference/nest_plugins_reference/payments/prepaid_credits.py)

[Agent Action Capsule]: https://datatracker.ietf.org/doc/draft-mih-scitt-agent-action-capsule/
