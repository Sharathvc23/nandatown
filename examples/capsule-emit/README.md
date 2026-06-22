# capsule-emit-nanda — verifiable, anchored records for NANDA agents

Two NANDA layer plugins that seal every agent interaction and payment into
a tamper-evident [Agent Action Capsule][] ledger — independently verifiable
by any third party without replaying the scenario.

| Layer | Plugin name | What it adds |
|-------|-------------|--------------|
| `trust` | `capsule_emit` | Drop-in for `agent_receipts`; seals every receipt to a capsule ledger. Ring-severance identical; adds third-party auditability. |
| `payments` | `stripe_capsule` | Stripe (or sandbox) payments; every payment sealed with `agent_input_digest` committing to amount + payer/payee at call time. |

## Install

```bash
pip install -e examples/capsule-emit   # from the nandatown repo root
nest plugins list | grep -E "trust|payments"
# capsule_emit   (trust)
# stripe_capsule (payments)
```

For real Stripe payments add `[stripe]`:

```bash
pip install -e "examples/capsule-emit[stripe]"
STRIPE_SECRET_KEY=sk_test_... nest run ./scenario.yaml
```

## Use in any scenario

```yaml
layers:
  trust: capsule_emit        # was: agent_receipts
  payments: stripe_capsule   # was: prepaid_credits
```

Run any scenario — all existing validators still pass, and a
`capsule_ledger.jsonl` appears alongside the trace:

```bash
agent-action-capsule verify --store capsule_ledger.jsonl   # exit 0
```

Each capsule's `agent_input_digest` is independently verifiable without
re-running the scenario. A tampered record produces a digest mismatch
that `verify` catches.

## Trust layer: `capsule_emit`

Identical ring-severance logic to `agent_receipts` plus an anchored
ledger gate: only receipts whose interactions were sealed to the capsule
ledger count toward an agent's reputation score. See
[`examples/capsule-trust/`](../capsule-trust/) for the full walkthrough.

## Payments layer: `stripe_capsule`

Sandbox by default (no `STRIPE_SECRET_KEY` required, no real charges).
Seals the Stripe `payment_intent_id`, amount, and outcome — if a client
later disputes the amount, re-derive the digest from the disputed values;
a mismatch is proof the amount was altered post-payment. See
[`examples/stripe-capsule-payment/`](../stripe-capsule-payment/) for the
full walkthrough.

## Demos

- **Receipt reputation with capsule ledger** — [`scenarios/receipt_reputation_capsule.yaml`](../../scenarios/receipt_reputation_capsule.yaml): the standard `receipt_reputation` scenario with `trust: capsule_emit`; ring-severance validators still pass.
- **Tax audit: cook the books, get caught** — [`examples/capsule-trust/`](../capsule-trust/#tax-audit-demo-cook-the-books-get-caught): capsule-sealed vs mutable ledger; auditor catch-rate 100% vs 0%.
- **Stripe payment → sealed capsule** — [`examples/stripe-capsule-payment/`](../stripe-capsule-payment/): one Stripe call, one verifiable capsule.

## Reference

- `capsule-emit` library: <https://github.com/action-state-group/capsule-emit>
- Agent Action Capsule spec: [draft-mih-scitt-agent-action-capsule][]
- Trust layer interface: [`docs/layers/trust.md`](../../docs/layers/trust.md)
- Payments layer interface: [`docs/layers/payments.md`](../../docs/layers/payments.md)
- Reference trust plugin to compare: [`agent_receipts.py`](../../packages/nest-plugins-reference/nest_plugins_reference/trust/agent_receipts.py)

[Agent Action Capsule]: https://datatracker.ietf.org/doc/draft-mih-scitt-agent-action-capsule/
[draft-mih-scitt-agent-action-capsule]: https://datatracker.ietf.org/doc/draft-mih-scitt-agent-action-capsule/
