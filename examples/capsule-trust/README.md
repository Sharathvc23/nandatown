# Trust layer: `capsule_emit`

Drop-in for `trust: agent_receipts` that adds a **verifiable, third-party-auditable
ledger** to any NANDA scenario. Every interaction report becomes a sealed
[Agent Action Capsule][] whose `agent_input_digest` is independently verifiable —
no agent self-report can be altered without the mismatch being detected.

## What this adds over `agent_receipts`

| | `agent_receipts` | `capsule_emit` |
|---|---|---|
| Collusion-ring severance | ✅ | ✅ (identical logic) |
| Cross-signed receipt verification | ✅ | ✅ |
| Immutable anchored ledger | ❌ | ✅ |
| Third-party audit without re-running | ❌ | ✅ |

## Install

```bash
pip install -e examples/capsule-emit   # from the nandatown repo root
nest plugins list | grep trust         # capsule_emit should appear
```

## Swap in any scenario YAML

```yaml
layers:
  trust: capsule_emit   # was: agent_receipts or score_average
```

Run against the bundled `receipt_reputation` scenario:

```bash
nest run scenarios/receipt_reputation_capsule.yaml
```

The `receipt_reputation` validators still pass — ring mean ≈ 0.0, honest
mean > 0.1 — and a `capsule_ledger.jsonl` appears alongside the trace:

```bash
agent-action-capsule verify --store capsule_ledger.jsonl   # exit 0 = all sealed correctly
```

## Tax audit demo: cook the books, get caught

A companion three-agent scenario (`tax_audit`) shows the deterrent
effect of capsule anchoring:

- **biz_control** — mutable ledger, cheats every cycle, auditor can't prove it
- **biz_capsule** — capsule-sealed ledger, every cheat is detectable via `agent_input_digest` mismatch
- **auditor** — re-derives the digest from the submitted amount; mismatch triggers a fine

Over 5000 cycles biz_capsule's cheat rate decays toward 0 (learns the
penalty); biz_control stays at 100% (no deterrent). The auditor's
catch rate is 100% for biz_capsule, 0% for biz_control — same record,
same incentive, only the record layer differs.

Full source and demo script:
[capsule-emit/examples/nanda-tax-audit](https://github.com/action-state-group/capsule-emit/tree/main/examples/nanda-tax-audit)

## Reference

- Plugin package: [`examples/capsule-emit/`](../capsule-emit/)
- `capsule-emit` repo: <https://github.com/action-state-group/capsule-emit>
- Trust layer interface: [`docs/layers/trust.md`](../../docs/layers/trust.md)
- Scenario YAML for this example: [`scenarios/receipt_reputation_capsule.yaml`](../../scenarios/receipt_reputation_capsule.yaml)
- Reference implementation to compare: [`agent_receipts.py`](../../packages/nest-plugins-reference/nest_plugins_reference/trust/agent_receipts.py)

[Agent Action Capsule]: https://datatracker.ietf.org/doc/draft-mih-scitt-agent-action-capsule/
