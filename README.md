# NEST — Network Environment for Swarm Testing

**NEST** is an open-source sandbox for testing agent protocols at scale. It is part of [NANDA](https://projectnanda.org), the Internet of AI Agents.

NEST lets a protocol designer swap any single layer of the agent stack — communication, coordination, payments, registries, identity, trust, and more — while keeping everything else as a default reference implementation. Then NEST spins up N agents, runs a scenario, injects failures, and reports what happened.

## Quick start

```bash
# Install
pip install nest-cli

# Run a scenario
nest run scenarios/marketplace.yaml

# Inspect the trace
nest inspect traces/marketplace.jsonl

# Check your setup
nest doctor
```

## The 12 pluggable layers

| Layer | What it does | Default plugin |
|---|---|---|
| Transport | How bytes move between agents | `in_memory` |
| Communication | Message format, request/response | `nest_native` |
| Identity | Agent identity and verification | `did_key` |
| Registry | How agents find each other | `in_memory` |
| Auth | Authentication and authorization | `jwt` |
| Trust | Reputation and attestation | `score_average` |
| Payments | How value moves | `prepaid_credits` |
| Coordination | How groups decide | `contract_net` |
| Negotiation | Bargaining between agents | `alternating_offers` |
| Memory | Shared state between agents | `blackboard` |
| Privacy | Encryption and zero-knowledge proofs | `noop` |
| Data Facts | Dataset metadata and exchange | `datafacts_v1` |

## Three fidelity tiers

- **Tier 1** — Pure simulation. State-machine agents, virtual clock, 10k+ agents, deterministic.
- **Tier 2** — Shell agent. Real LLM-backed agents (via litellm), 10–100 agents.
- **Tier 3** — BYO container. Bring your own Docker image. (Post-MVP)

Same interfaces, same scenarios, same observability across all tiers.

## Writing a plugin

A plugin implements one layer interface and registers via entry points:

```python
from nest_sdk import Payments

class MyPaymentProtocol(Payments):
    async def quote(self, service):
        ...
```

```toml
# pyproject.toml
[project.entry-points."nest.plugins.payments"]
my_payment = "my_pkg:MyPaymentProtocol"
```

Test conformance:

```bash
nest plugins conform my_pkg
```

## Project structure

```
nest/
├── packages/
│   ├── nest-core/          # Engine, event loop, layer interfaces
│   ├── nest-sdk/           # Public API for plugin authors
│   ├── nest-cli/           # CLI: nest run, nest inspect, etc.
│   ├── nest-mocks/         # In-memory mock services for testing
│   ├── nest-shell/         # Tier 2 LLM-backed agent
│   ├── nest-scenarios/     # Reference task scenarios
│   └── nest-plugins-reference/  # Default plugins per layer
├── apps/
│   └── dashboard/          # Next.js observability UI
├── docs/                   # Documentation
└── examples/               # Plugin authoring templates
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
