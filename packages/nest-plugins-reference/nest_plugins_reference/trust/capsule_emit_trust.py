# SPDX-License-Identifier: Apache-2.0
"""CapsuleEmitTrust — NANDA Town trust plugin backed by capsule-emit.

Drop-in replacement for ``agent_receipts``: every interaction a NANDA agent
already reports via ``ctx.plugins.get("trust").report(...)`` is anchored to
an Agent Action Capsule ledger — zero agent-code changes required.

Three gates for a receipt to build reputation (same as ``agent_receipts``):

1. **Valid** — Ed25519 issuer signature verifies.
2. **Corroborated** — distinct counterparty co-signed the same interaction.
3. **Anchored** — a capsule was emitted and is present in the capsule ledger.

Gate 3 is the additive contribution: an agent whose interactions are never
anchored gets no reputation score even if their receipts are individually
valid and corroborated. The capsule ledger is the authoritative record,
independently verifiable by any party who ran none of the agents.

Plain-string ``evidence.detail`` (stock NANDA scenarios with no receipt)
falls back to the ``score_average`` heuristic so this plugin is a drop-in
in any scenario.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, cast

import capsule_emit  # type: ignore[import-untyped]
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from nest_core.types import AgentId, Attestation, Claim, Evidence, ReputationScore, Signature

from nest_plugins_reference.trust.agent_receipts import (
    AgentReceiptsTrust,
    did_for_pubkey,
    is_corroborated,
)

logger = logging.getLogger(__name__)

ALGORITHM = "ed25519"
_DEFAULT_CAPSULE_ACTION = "message_sent"


# ---------------------------------------------------------------------------
# Local helpers — reimplements private agent_receipts helpers to avoid
# importing underscore-prefixed names across module boundaries.
# ---------------------------------------------------------------------------


def _action_field(receipt: dict[str, Any], key: str) -> Any:
    action = receipt.get("action")
    if isinstance(action, dict):
        return cast("dict[str, Any]", action).get(key)
    return None


def _counterparty(receipt: dict[str, Any]) -> str | None:
    cp = _action_field(receipt, "counterparty_did")
    if isinstance(cp, str) and cp and cp != receipt.get("issuer_did"):
        return cp
    return None


def _verify_receipt(receipt: dict[str, Any]) -> bool:
    """Return True iff the receipt's issuer Ed25519 signature verifies."""
    issuer = receipt.get("issuer_did")
    sig = receipt.get("signature")
    if not isinstance(issuer, str) or not isinstance(sig, str):
        return False
    core: dict[str, Any] = {k: v for k, v in receipt.items() if k != "signature"}
    evidence = core.get("evidence")
    if isinstance(evidence, dict):
        trimmed: dict[str, Any] = {
            k: v for k, v in cast("dict[str, Any]", evidence).items() if k != "witness_signatures"
        }
        if trimmed:
            core["evidence"] = trimmed
        else:
            del core["evidence"]
    payload = json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(issuer)).verify(
            bytes.fromhex(sig), payload
        )
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


class CapsuleEmitTrust:
    """Anchored, collusion-resistant reputation implementing the ``Trust`` Protocol.

    Mirrors ``AgentReceiptsTrust`` with one addition: every corroborated receipt
    triggers a ``capsule_emit.emit()`` call, so the reputation history is sealed
    to an Agent Action Capsule ledger that any third party can verify with::

        agent-action-capsule verify --store capsule_ledger.jsonl

    Args:
        identity: Agent identity (passed by the NANDA runtime; may be None).
        anchor: Whether to anchor capsules to the public log (default False for
            deterministic replay; set True for the live-anchor pass).
        ledger: Path for the capsule ledger JSONL file.
    """

    _SYSTEM_AGENT = AgentId("trust:capsule_emit")

    def __init__(
        self,
        identity: Any = None,
        *,
        anchor: bool = False,
        ledger: str | Path = "capsule_ledger.jsonl",
    ) -> None:
        self._identity = identity
        self._anchor = anchor
        self._ledger_path = Path(ledger)
        self._system_seed = hashlib.sha256(b"trust:capsule_emit").digest()[:32]
        self._base_trust = AgentReceiptsTrust(identity)
        self._receipts: list[dict[str, Any]] = []
        self._anchored: dict[tuple[str, str, str], str] = {}

    def _did_of(self, agent: AgentId) -> str:
        seed = hashlib.sha256(str(agent).encode()).digest()[:32]
        pub = (
            Ed25519PrivateKey.from_private_bytes(seed)
            .public_key()
            .public_bytes(Encoding.Raw, PublicFormat.Raw)
        )
        return did_for_pubkey(pub)

    def _receipt_key(self, receipt: dict[str, Any]) -> tuple[str, str, str]:
        issuer = str(receipt.get("issuer_did", ""))
        cp = _counterparty(receipt) or ""
        action_id = str(
            _action_field(receipt, "action_id") or _action_field(receipt, "category") or ""
        )
        return (issuer, cp, action_id)

    async def report(self, agent: AgentId, evidence: Evidence) -> None:
        """Report evidence; anchor to capsule ledger if it is a valid receipt."""
        await self._base_trust.report(agent, evidence)
        try:
            parsed: object = json.loads(evidence.detail)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(parsed, dict):
            return
        receipt = cast("dict[str, Any]", parsed)
        if not _verify_receipt(receipt):
            return
        self._receipts.append(receipt)
        await asyncio.to_thread(self._emit_capsule, agent, receipt)

    def _emit_capsule(self, agent: AgentId, receipt: dict[str, Any]) -> None:
        issuer_did = str(receipt.get("issuer_did", ""))
        category = str(_action_field(receipt, "category") or _DEFAULT_CAPSULE_ACTION)
        cp_did = _counterparty(receipt) or ""
        corroborated = is_corroborated(receipt)
        try:
            result = capsule_emit.emit(  # pyright: ignore[reportUnknownMemberType]
                action=category,
                operator=issuer_did,
                developer=str(agent),
                agent_input=receipt,
                agent_output={"corroborated": corroborated, "counterparty_did": cp_did},
                anchor=self._anchor,
                ledger=str(self._ledger_path),
            )
            self._anchored[self._receipt_key(receipt)] = result.capsule_id
        except Exception:
            logger.exception("capsule emit failed for agent=%s", agent)

    async def score(self, agent: AgentId) -> ReputationScore:
        """Reputation from corroborated, ring-severed, anchored receipts.

        Delegates collusion-ring severance to the base ``AgentReceiptsTrust``,
        then applies the anchor gate: confidence scales with the fraction of
        this agent's receipts that were successfully anchored.
        """
        base = await self._base_trust.score(agent)
        did = self._did_of(agent)
        mine_all = [r for r in self._receipts if str(r.get("issuer_did", "")) == did]
        if not mine_all:
            return base
        mine_anchored = [r for r in mine_all if self._receipt_key(r) in self._anchored]
        anchor_ratio = len(mine_anchored) / len(mine_all)
        return ReputationScore(
            agent_id=agent,
            score=base.score * anchor_ratio,
            confidence=base.confidence * anchor_ratio,
            sample_count=base.sample_count,
        )

    async def attest(self, agent: AgentId, claim: Claim) -> Attestation:
        """Issue an Ed25519-signed attestation (same shape as agent_receipts)."""
        sk = Ed25519PrivateKey.from_private_bytes(self._system_seed)
        raw = sk.sign(claim.model_dump_json().encode())
        sig = Signature(signer=self._SYSTEM_AGENT, value=raw, algorithm=ALGORITHM)
        return Attestation(issuer=self._SYSTEM_AGENT, claim=claim, signature=sig)

    async def stake(self, agent: AgentId, amount: int) -> None:
        await self._base_trust.stake(agent, amount)
