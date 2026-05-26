# NEST Hackathon Brief — Layer-Enumerated Track

You are participating in the NEST research hackathon. NEST is a discrete-event
simulator for multi-agent system research, organised around a stack of
protocol layers.

**Task**: Pick exactly one of the 12 protocol layers below, and improve it.
Submit a single PR.

## The 12 layers

The full descriptions live in `docs/layers/`:

- `auth` — agent authentication
- `communication` — message passing
- `coordination` — multi-agent coordination primitives
- `datafacts` — shared facts / world model
- `identity` — agent identity & key management
- `memory` — per-agent memory
- `negotiation` — proposal / counter-proposal flows
- `payments` — value transfer
- `privacy` — selective disclosure
- `registry` — service discovery
- `transport` — packet delivery & reliability
- `trust` — reputation, EigenTrust, etc.

Read the layer doc before you commit. Pick the one most interesting to *you*.

## Submission rules

- Branch name: `hackathon/<layer>-<short-handle>` (e.g.
  `hackathon/trust-eigen-improvements`).
- Do not push to `main`, `master`, `hackathon/*` (other branches), or
  `claude/*`.
- Before you push, run all five local checks; the PR must be green on first
  push:
  - `uv sync`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run pyright`
  - `uv run pytest -v`
- PR body must state:
  - which layer you chose,
  - what you changed,
  - why it matters for that layer's research questions.

## What "improve" means here

A good submission either: (1) adds a primitive/algorithm to the layer with
tests, (2) ships a benchmark/scenario that stresses the layer, or (3)
identifies and fixes a latent bug. Aim for ~150-400 lines of net change.
