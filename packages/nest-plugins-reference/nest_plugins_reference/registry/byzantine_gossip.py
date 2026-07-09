# SPDX-License-Identifier: Apache-2.0
"""Byzantine-resistant gossip registry plugin — scaffold (Task 1 of the series).

``nest_plugins_reference.registry.gossip.GossipRegistry`` gives us
eventually-consistent discovery under honest-but-partitioned failures: every
agent gossips its local view over the transport, and the simulator's
partition logic naturally blocks cross-partition propagation.  It assumes,
however, that every participant plays by the rules — same publisher never
signs two conflicting write tags at the same version, no agent forges
another agent's cards, and no agent tries to starve a victim's view by only
ever gossiping with a captured subset of peers.

This plugin is the byzantine-hardened counterpart.  Task 1 only scaffolds
the class and proves it satisfies ``nest_core.layers.registry.Registry`` —
the view/merge/wire-format machinery is a deliberate copy of
``GossipRegistry``'s structure (this task is a pure scaffold; nothing
security-relevant changes yet), while the network-wide primitives
(``GossipNetwork``, ``GOSSIP_PREFIX``, ``OP_DIGEST``, ``OP_PUSH``,
``_WriteTag``) are imported and reused as-is so both plugins share one
notion of "peer set" and "write ordering." Later tasks in this series layer
the actual byzantine resistance on top of this scaffold:

* Task 2 — signed write tags + signature verification on merge.
* Task 3 — equivocation detection (same publisher, same version, two
  different payloads) and quarantine of the equivocating publisher.
* Task 4 — eclipse-resistant peer sampling + adversarial scenarios and
  validators.

The constructor therefore already takes an ``Identity`` so later tasks can
sign outgoing write tags and verify inbound ones without changing the
public API again.

Example::

    from nest_plugins_reference.identity.did_key import DidKeyIdentity
    from nest_plugins_reference.registry.gossip import GossipNetwork

    net = GossipNetwork(agent_ids=[AgentId("a"), AgentId("b")])
    identity = DidKeyIdentity(AgentId("a"), seed=b"s")
    reg = ByzantineGossipRegistry(AgentId("a"), net, identity)
    await reg.register(AgentCard(agent_id=AgentId("a"), name="A"))
"""

from __future__ import annotations

import json
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nest_core.types import AgentCard, AgentId, Query

from nest_plugins_reference.registry.gossip import (
    GOSSIP_PREFIX,
    OP_DIGEST,
    OP_PUSH,
    GossipNetwork,
    _WriteTag,  # pyright: ignore[reportPrivateUsage]
)

if TYPE_CHECKING:
    from nest_core.layers.identity import Identity
    from nest_core.sim.agent import AgentContext


@dataclass
class _Versioned:
    """A stored card plus its write tag and a tombstone bit.

    Local copy of ``GossipRegistry``'s ``_Versioned`` structure — kept
    separate (not imported) so later tasks can extend it with a signature
    field without touching the plain gossip plugin.

    Example::

        v = _Versioned(card=card, tag=_WriteTag(1, AgentId("a")), tombstone=False)
    """

    card: AgentCard
    tag: _WriteTag
    tombstone: bool = False


class ByzantineGossipRegistry:
    """Per-agent gossip registry, scaffolded for byzantine resistance.

    Satisfies ``nest_core.layers.registry.Registry``: ``register``,
    ``lookup``, ``subscribe``, ``deregister``.  Task 1 delegates to the same
    local-view / last-writer-wins merge logic as
    ``nest_plugins_reference.registry.gossip.GossipRegistry`` — no
    signature verification, equivocation detection, or eclipse resistance
    yet.  Those land in Tasks 2-4 of this series, on top of this scaffold.

    Driver agents call ``gossip_round(ctx)`` on a schedule and forward
    inbound ``GOSSIP_PREFIX``-marked payloads to
    ``handle_gossip(sender, payload, ctx)``, exactly as with
    ``GossipRegistry``.

    Example::

        net = GossipNetwork(agent_ids=[AgentId("a"), AgentId("b")])
        identity = DidKeyIdentity(AgentId("a"), seed=b"s")
        reg = ByzantineGossipRegistry(AgentId("a"), net, identity)
        await reg.register(AgentCard(agent_id=AgentId("a"), name="A"))
        cards = await reg.lookup(Query())  # returns local view only
    """

    def __init__(self, agent_id: AgentId, network: GossipNetwork, identity: Identity) -> None:
        self._agent_id = agent_id
        self._network = network
        self._identity = identity
        self._view: dict[AgentId, _Versioned] = {}

    # ------------------------------------------------------------------
    # Registry protocol
    # ------------------------------------------------------------------

    async def register(self, card: AgentCard) -> None:
        """Register ``card`` locally; gossip propagates it on the next round.

        Example::

            await reg.register(AgentCard(agent_id=AgentId("a"), name="A"))
        """
        tag = _WriteTag(
            version=self._network.next_version(card.agent_id),
            publisher_id=card.agent_id,
        )
        self._apply(card, tag, tombstone=False)

    async def lookup(self, query: Query) -> list[AgentCard]:
        """Return cards matching ``query`` from the **local** view.

        Example::

            cards = await reg.lookup(Query(capabilities=["sell"]))
        """
        return [v.card for v in self._view.values() if not v.tombstone and _matches(v.card, query)]

    async def subscribe(self, query: Query) -> AsyncIterator[AgentCard]:
        """Yield cards matching ``query`` from the local view, then end.

        Example::

            async for card in reg.subscribe(query):
                print(card.name)
        """
        for card in await self.lookup(query):
            yield card

    async def deregister(self, agent: AgentId) -> None:
        """Tombstone ``agent`` locally; gossip propagates the tombstone.

        Example::

            await reg.deregister(AgentId("a"))
        """
        existing = self._view.get(agent)
        if existing is None:
            return
        tag = _WriteTag(
            version=self._network.next_version(agent),
            publisher_id=agent,
        )
        self._apply(existing.card, tag, tombstone=True)

    # ------------------------------------------------------------------
    # Gossip mechanics
    # ------------------------------------------------------------------

    async def gossip_round(self, ctx: AgentContext) -> None:
        """Run one round of push-pull anti-entropy.

        Same peer-sampling strategy as ``GossipRegistry.gossip_round`` for
        now; Task 4 replaces the uniform sample with an eclipse-resistant
        one.

        Example::

            await reg.gossip_round(ctx)
        """
        peers = self._network.peers_of(self._agent_id)
        if not peers:
            return
        fanout = min(self._network.fanout, len(peers))
        chosen = _sample_without_replacement(ctx.rng, peers, fanout)
        digest = self._digest()
        payload = GOSSIP_PREFIX + OP_DIGEST + _encode(digest)
        for peer in chosen:
            await ctx.send(peer, payload)

    async def handle_gossip(self, sender: AgentId, payload: bytes, ctx: AgentContext) -> bool:
        """Process a gossip message from ``sender``.

        Returns ``True`` if the payload was a gossip message (and was
        consumed), ``False`` otherwise.  No signature verification or
        equivocation detection yet — see Tasks 2-3.

        Example::

            handled = await reg.handle_gossip(sender, payload, ctx)
        """
        if not payload.startswith(GOSSIP_PREFIX):
            return False
        body = payload[len(GOSSIP_PREFIX) :]
        if not body:
            return True
        op, rest = body[:1], body[1:]
        if op == OP_DIGEST:
            sender_digest = _decode_digest(rest)
            missing = self._compute_missing(sender_digest)
            if missing:
                push_payload = GOSSIP_PREFIX + OP_PUSH + _encode_push(missing)
                await ctx.send(sender, push_payload)
            return True
        if op == OP_PUSH:
            for card, tag, tombstone in _decode_push(rest):
                self._apply(card, tag, tombstone=tombstone)
            return True
        return True  # Unknown op: consume silently so junk doesn't escape.

    # ------------------------------------------------------------------
    # Inspection (used by validators + tests)
    # ------------------------------------------------------------------

    def view_snapshot(self) -> dict[AgentId, tuple[int, AgentId, bool]]:
        """Return a deterministic snapshot of the local view.

        Same shape as ``GossipRegistry.view_snapshot`` so
        ``check_converged`` composes across both plugins.

        Example::

            snap = reg.view_snapshot()
        """
        return {
            aid: (v.tag.version, v.tag.publisher_id, v.tombstone)
            for aid, v in sorted(self._view.items())
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply(self, card: AgentCard, tag: _WriteTag, *, tombstone: bool) -> None:
        existing = self._view.get(card.agent_id)
        if existing is not None and existing.tag >= tag:
            return
        self._view[card.agent_id] = _Versioned(card=card, tag=tag, tombstone=tombstone)

    def _digest(self) -> dict[AgentId, _WriteTag]:
        return {aid: v.tag for aid, v in self._view.items()}

    def _compute_missing(
        self, sender_digest: dict[AgentId, _WriteTag]
    ) -> list[tuple[AgentCard, _WriteTag, bool]]:
        out: list[tuple[AgentCard, _WriteTag, bool]] = []
        for aid, versioned in self._view.items():
            sender_tag = sender_digest.get(aid)
            if sender_tag is None or sender_tag < versioned.tag:
                out.append((versioned.card, versioned.tag, versioned.tombstone))
        return out


# ---------------------------------------------------------------------------
# Helpers (module-private; structural copy of gossip.py's wire codec)
# ---------------------------------------------------------------------------


def _matches(card: AgentCard, query: Query) -> bool:
    if query.capabilities and not all(cap in card.capabilities for cap in query.capabilities):
        return False
    return not (query.name_pattern and query.name_pattern not in card.name)


def _sample_without_replacement(rng: random.Random, peers: list[AgentId], k: int) -> list[AgentId]:
    """Deterministic sample of ``k`` peers from ``peers`` using ``rng``.

    Structural copy of ``gossip.py``'s Fisher-Yates sampler.  Task 4
    replaces this with the eclipse-resistant sampler.
    """
    pool = list(peers)
    out: list[AgentId] = []
    for _ in range(k):
        j = rng.randint(0, len(pool) - 1)
        out.append(pool[j])
        pool[j] = pool[-1]
        pool.pop()
    return out


def _encode(digest: dict[AgentId, _WriteTag]) -> bytes:
    obj = {str(aid): [t.version, str(t.publisher_id)] for aid, t in digest.items()}
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _decode_digest(raw: bytes) -> dict[AgentId, _WriteTag]:
    obj = json.loads(raw.decode())
    return {
        AgentId(aid): _WriteTag(version=int(v), publisher_id=AgentId(pid))
        for aid, (v, pid) in obj.items()
    }


def _encode_push(items: list[tuple[AgentCard, _WriteTag, bool]]) -> bytes:
    obj = [
        {
            "card": card.model_dump(mode="json"),
            "version": tag.version,
            "publisher": str(tag.publisher_id),
            "tombstone": tombstone,
        }
        for card, tag, tombstone in items
    ]
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _decode_push(raw: bytes) -> list[tuple[AgentCard, _WriteTag, bool]]:
    obj: list[dict[str, object]] = json.loads(raw.decode())
    out: list[tuple[AgentCard, _WriteTag, bool]] = []
    for entry in obj:
        card = AgentCard.model_validate(entry["card"])
        tag = _WriteTag(
            version=int(entry["version"]),  # type: ignore[arg-type]
            publisher_id=AgentId(str(entry["publisher"])),
        )
        out.append((card, tag, bool(entry["tombstone"])))
    return out
