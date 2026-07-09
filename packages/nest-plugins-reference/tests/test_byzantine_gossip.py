# SPDX-License-Identifier: Apache-2.0
"""Conformance tests for the byzantine_gossip registry plugin scaffold.

Task 1 only proves the plugin resolves via ``PluginRegistry`` and conforms
to the ``Registry`` Protocol.  Byzantine-resistance (signatures, equivocation
detection, eclipse resistance) is added in later tasks.
"""

from __future__ import annotations

from nest_core.layers.registry import Registry
from nest_core.plugins import PluginRegistry
from nest_core.types import AgentId
from nest_plugins_reference.identity.did_key import DidKeyIdentity
from nest_plugins_reference.registry.gossip import GossipNetwork


def test_resolves_and_conforms() -> None:
    cls = PluginRegistry().resolve("registry", "byzantine_gossip")
    net = GossipNetwork(agent_ids=[AgentId("a"), AgentId("b")])
    reg = cls(AgentId("a"), net, DidKeyIdentity(AgentId("a"), seed=b"s"))
    assert isinstance(reg, Registry)
