# SPDX-License-Identifier: Apache-2.0
"""Identity key-rotation scenario with byzantine forgery/backdating attackers.

Honest agents sign heartbeat messages with a real Ed25519 key
(``ed25519_rotating`` plugin), rotate that key once mid-run, and keep signing
under the new key. Byzantine agents (``failures.byzantine_agents`` fraction,
default 10%) attempt the two attacks the plugin is built to defeat:

* **post-rotation forgery** — forge a fresh signature with their *own* stale,
  rotated-out key after rotation, and
* **backdating** — sign with the *new* key but claim the signature belongs in
  the old key's window.

Every signing/rotation event is emitted into the trace in a line-protocol the
``identity_rotation`` validator parses (see
``nest_core.validators.validate_identity_rotation``). The validator anchors
every as-of check to the trace's externally-observed ``ts`` — never to the
attacker-controlled claimed tick — so both attacks are caught.

Trace line protocol (carried in message bodies, ``:``-delimited):

* ``rotate:<agent>:<old_key_id>:<new_key_id>:<rotate_tick>`` — a rotation; the
  old key's window closes at ``rotate_tick`` and the new key's window opens.
* ``signed:<agent>:<key_id>:<claimed_tick>:<verdict>`` — a signed heartbeat
  ``verdict`` is ``ok`` (honest), ``forge`` (post-rotation forgery), or
  ``backdate`` (claimed tick moved into a closed window).

Example::

    agents = identity_rotation_factory(config, plugins)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nest_core.scenario import ScenarioConfig
from nest_core.sim.agent import AgentContext, StateMachineAgent
from nest_core.types import AgentId

if TYPE_CHECKING:
    from nest_plugins_reference.identity.ed25519_rotating import (
        Ed25519RotatingIdentity,
    )


def _make_identity(agent_id: AgentId, seed: bytes) -> Ed25519RotatingIdentity:
    """Construct a fresh rotating identity for *agent_id* (deterministic seed)."""
    from nest_plugins_reference.identity.ed25519_rotating import (
        Ed25519RotatingIdentity,
    )

    return Ed25519RotatingIdentity(agent_id, seed=seed)


class HonestSigner(StateMachineAgent):
    """Signs heartbeats, rotates its key once mid-run, keeps signing.

    Emits ``rotate:`` and ``signed:...:ok`` lines so the validator can rebuild
    key windows and confirm every honest signature sits inside a valid window.

    Example::

        agent = HonestSigner(AgentId("signer-0"), AgentId("auditor-0"), rounds=6)
    """

    def __init__(
        self,
        agent_id: AgentId,
        auditor: AgentId,
        rounds: int = 6,
        rotate_at_round: int = 3,
    ) -> None:
        self._id = agent_id
        self._auditor = auditor
        self._rounds = rounds
        self._rotate_at_round = rotate_at_round
        self._round = 0
        self._ident = _make_identity(agent_id, seed=b"honest:" + str(agent_id).encode())

    async def _emit_round(self, ctx: AgentContext) -> None:
        self._round += 1
        self._ident.set_clock(ctx.time)
        if self._round == self._rotate_at_round:
            rec = self._ident.rotate_key(b"rot:" + str(self._id).encode())
            await ctx.send(
                self._auditor,
                f"rotate:{self._id}:{rec.old_key_id}:{rec.new_key_id}:{ctx.time}".encode(),
            )
        sig = self._ident.sign(f"heartbeat:{self._id}:{self._round}".encode())
        await ctx.send(
            self._auditor,
            f"signed:{self._id}:{sig.key_id}:{sig.signed_at}:ok".encode(),
        )

    async def on_start(self, ctx: AgentContext) -> None:
        await self._emit_round(ctx)

    async def on_message(self, ctx: AgentContext, sender: AgentId, payload: bytes) -> None:
        msg = payload.decode("utf-8", errors="replace")
        if msg.startswith("tick:") and self._round < self._rounds:
            await self._emit_round(ctx)


class ByzantineSigner(StateMachineAgent):
    """Rotates, then attempts post-rotation forgery and backdating.

    The attacker holds its *own* old key (the realistic "key was compromised"
    threat) and tries both attacks. Each attack is emitted with the **true**
    observed tick as the trace ``ts`` but a falsified claimed tick / stale
    ``key_id`` — exactly the data the validator uses to reject it.

    Example::

        agent = ByzantineSigner(AgentId("byz-0"), AgentId("auditor-0"), rounds=6)
    """

    def __init__(
        self,
        agent_id: AgentId,
        auditor: AgentId,
        rounds: int = 6,
        rotate_at_round: int = 3,
    ) -> None:
        self._id = agent_id
        self._auditor = auditor
        self._rounds = rounds
        self._rotate_at_round = rotate_at_round
        self._round = 0
        self._old_key_id = ""
        self._ident = _make_identity(agent_id, seed=b"byz:" + str(agent_id).encode())

    async def _emit_round(self, ctx: AgentContext) -> None:
        self._round += 1
        self._ident.set_clock(ctx.time)
        if self._round == self._rotate_at_round:
            self._old_key_id = str(self._ident.current_key_id)
            rec = self._ident.rotate_key(b"rot:" + str(self._id).encode())
            await ctx.send(
                self._auditor,
                f"rotate:{self._id}:{rec.old_key_id}:{rec.new_key_id}:{ctx.time}".encode(),
            )

        if self._round <= self._rotate_at_round:
            # Behave honestly until the key has rotated out.
            sig = self._ident.sign(f"heartbeat:{self._id}:{self._round}".encode())
            await ctx.send(
                self._auditor,
                f"signed:{self._id}:{sig.key_id}:{sig.signed_at}:ok".encode(),
            )
            return

        # Attack A: post-rotation forgery with the stale, rotated-out key.
        from nest_plugins_reference.identity.ed25519_rotating import KeyId

        forged = self._ident.sign_with(
            f"forged:{self._id}:{self._round}".encode(), KeyId(self._old_key_id)
        )
        await ctx.send(
            self._auditor,
            f"signed:{self._id}:{forged.key_id}:{forged.signed_at}:forge".encode(),
        )

        # Attack B: backdating — sign with the new key but claim an old tick.
        sig = self._ident.sign(f"backdated:{self._id}:{self._round}".encode())
        backdated_tick = 0.0  # claim it sits at the very start (old key's window)
        await ctx.send(
            self._auditor,
            f"signed:{self._id}:{sig.key_id}:{backdated_tick}:backdate".encode(),
        )

    async def on_start(self, ctx: AgentContext) -> None:
        await self._emit_round(ctx)

    async def on_message(self, ctx: AgentContext, sender: AgentId, payload: bytes) -> None:
        msg = payload.decode("utf-8", errors="replace")
        if msg.startswith("tick:") and self._round < self._rounds:
            await self._emit_round(ctx)


class AuditorAgent(StateMachineAgent):
    """Drives rounds and records signatures; the trace is the audit log.

    The auditor pulses every signer once per round (``tick:`` messages) so the
    simulation advances deterministically. All real verification happens
    offline in the ``identity_rotation`` validator against the emitted trace.

    Example::

        auditor = AuditorAgent(AgentId("auditor-0"), signers, rounds=6)
    """

    def __init__(self, agent_id: AgentId, signers: list[AgentId], rounds: int = 6) -> None:
        self._id = agent_id
        self._signers = signers
        self._rounds = rounds
        self._pulses = 0

    async def on_start(self, ctx: AgentContext) -> None:
        # First round is kicked off by each signer's own on_start; schedule the
        # remaining pulses.
        await self._pulse(ctx)

    async def _pulse(self, ctx: AgentContext) -> None:
        self._pulses += 1
        if self._pulses >= self._rounds:
            return
        for signer in self._signers:
            await ctx.send(signer, f"tick:{self._pulses}".encode())

    async def on_message(self, ctx: AgentContext, sender: AgentId, payload: bytes) -> None:
        msg = payload.decode("utf-8", errors="replace")
        # Advance to the next round once we have heard from the first signer.
        if msg.startswith("signed:") and sender == self._signers[0]:
            await self._pulse(ctx)


def identity_rotation_factory(
    config: ScenarioConfig,
    plugins: dict[str, Any],
) -> dict[AgentId, StateMachineAgent]:
    """Create honest + byzantine signers and one auditor.

    The byzantine fraction comes from ``failures.byzantine_agents`` (default
    0.10). Each signer rotates its key once at ``rotate_at_round``.

    Example::

        agents = identity_rotation_factory(config, plugins)
    """
    task_config = config.task.config
    rounds = int(task_config.get("rounds", 6))
    rotate_at_round = int(task_config.get("rotate_at_round", 3))
    byzantine_fraction = config.failures.byzantine_agents or task_config.get(
        "byzantine_fraction", 0.10
    )

    signer_count = max(1, config.agents.count - 1)
    byzantine_count = int(signer_count * byzantine_fraction)
    honest_count = signer_count - byzantine_count

    if config.agents.roles:
        for role in config.agents.roles:
            if role.name == "honest":
                honest_count = role.count
            elif role.name == "byzantine":
                byzantine_count = role.count

    auditor_id = AgentId("auditor-0")
    signers: list[AgentId] = [AgentId(f"signer-{i}") for i in range(honest_count)]
    signers += [AgentId(f"byz-{i}") for i in range(byzantine_count)]

    agents: dict[AgentId, StateMachineAgent] = {}
    for i in range(honest_count):
        aid = AgentId(f"signer-{i}")
        agents[aid] = HonestSigner(
            aid, auditor=auditor_id, rounds=rounds, rotate_at_round=rotate_at_round
        )
    for i in range(byzantine_count):
        aid = AgentId(f"byz-{i}")
        agents[aid] = ByzantineSigner(
            aid, auditor=auditor_id, rounds=rounds, rotate_at_round=rotate_at_round
        )

    agents[auditor_id] = AuditorAgent(auditor_id, signers=signers, rounds=rounds)
    return agents
