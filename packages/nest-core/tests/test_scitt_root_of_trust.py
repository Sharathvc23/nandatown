# SPDX-License-Identifier: Apache-2.0
"""Root-of-trust acceptance tests for the anchoring validator.

THE acceptance gate for the SCITT root-of-trust rework, written FIRST (before
the fix). The hole: the on-trace seal ``seal:<seq>:<subject_digest>:<chain_hash>``
is unsigned and ``subject_digest`` is a pure function of plaintext receipt
content already on the trace — so a party that anchors NOTHING can recompute
the digests, rebuild the hash chain, and emit a seal set the validator grades
PASS. The evidence is authored by the party under test (self-authored evidence).

These tests assert the property the validator MUST have: anchoring evidence is
only acceptable when it is authored by an independent third-party SCITT
Transparency Service whose private key the participant does not hold — i.e. a
COSE receipt (RFC 9162 inclusion proof, signature over the tree head) that
verifies against a pinned TS public key. Fabricated seals carry no valid TS
signature, so every forgery below must grade FAIL.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from nest_core.canonical import SEAL_CHAIN_GENESIS, jcs_digest, seal_chain
from nest_core.validators import validate_receipt_reputation_anchored
from nest_plugins_reference.trust.agent_receipts import (
    cosign_receipt,
    did_for_pubkey,
    sign_receipt,
)

# ---------------------------------------------------------------------------
# Plaintext-only helpers: everything below is computable by ANY trace reader.
# No Transparency-Service key material appears anywhere in this file — that is
# the point: a forger has exactly these inputs and nothing else.
# ---------------------------------------------------------------------------


def _seed(label: str) -> bytes:
    return hashlib.sha256(label.encode()).digest()[:32]


def _did(label: str) -> str:
    pub = (
        Ed25519PrivateKey.from_private_bytes(_seed(label))
        .public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    return did_for_pubkey(pub)


def _corroborated_receipt(issuer_label: str, cp_label: str, rid: str) -> dict[str, Any]:
    r: dict[str, Any] = {
        "receipt_id": rid,
        "issuer_did": _did(issuer_label),
        "action": {"category": "purchase", "counterparty_did": _did(cp_label)},
    }
    r = sign_receipt(r, issuer_seed=_seed(issuer_label))
    return cosign_receipt(r, counterparty_seed=_seed(cp_label))


def _receipts() -> list[dict[str, Any]]:
    return [
        _corroborated_receipt("issuer-a", "cp-a", "r0"),
        _corroborated_receipt("issuer-b", "cp-b", "r1"),
        _corroborated_receipt("issuer-c", "cp-c", "r2"),
    ]


def _receipt_event(receipt: dict[str, Any], agent: str = "honest-0") -> dict[str, Any]:
    return {"agent": agent, "kind": "send", "msg": "receipt:" + json.dumps(receipt), "ts": 0.0}


def _score_event() -> dict[str, Any]:
    return {
        "agent": "auditor-0",
        "kind": "broadcast",
        "msg": "score:honest-0:0.632121:1.000000:honest",
        "ts": 1.0,
    }


def _forged_seal_events(
    receipts: list[dict[str, Any]], agent: str = "mallory-0"
) -> list[dict[str, Any]]:
    """THE forgery: rebuild a chain-valid seal set from plaintext trace content.

    This is exactly what a non-anchoring party (any registered plugin, or any
    agent via ``ctx.broadcast``) can do: read the ``receipt:`` lines, recompute
    each JCS digest, refold the public hash chain, and broadcast the seals. It
    anchors nothing and signs nothing.
    """
    chain = SEAL_CHAIN_GENESIS
    events: list[dict[str, Any]] = []
    for seq, r in enumerate(receipts):
        digest = jcs_digest(r)
        chain = seal_chain(chain, digest)
        events.append(
            {
                "agent": agent,
                "kind": "broadcast",
                "msg": f"seal:{seq}:{digest}:{chain}",
                "ts": 1.0,
            }
        )
    return events


def _anchored(events: list[dict[str, Any]]) -> Any:
    results = validate_receipt_reputation_anchored(events)
    matched = [r for r in results if r.name == "receipt_reputation_anchored"]
    assert matched, "receipt_reputation_anchored validator returned no result"
    return matched[0]


# ---------------------------------------------------------------------------
# The acceptance gate: forged seals from plaintext MUST grade FAIL
# ---------------------------------------------------------------------------


def test_forged_seal_events_from_plaintext_fail() -> None:
    """A non-anchoring party's fabricated seal set must grade FAIL.

    The trace carries valid receipts plus seals forged purely from their
    plaintext — no Transparency Service signed anything. If this grades PASS,
    the gate accepts self-authored evidence and the anchoring property is void.
    """
    receipts = _receipts()
    events = [_receipt_event(r) for r in receipts]
    events.append(_score_event())
    events.extend(_forged_seal_events(receipts))

    result = _anchored(events)
    assert not result.passed, (
        "FORGERY ACCEPTED: a party that anchors nothing fabricated a chain-valid "
        "seal set from plaintext trace content and the validator graded it PASS. "
        f"detail={result.detail!r}"
    )


def test_forged_seals_attributed_to_auditor_fail() -> None:
    """Same forgery with the seal events attributed to ``auditor-0`` must FAIL.

    Emitter attribution is not a root of trust either — nothing stops a
    participant-supplied plugin from emitting under the auditor's flow. Only a
    third-party TS signature over the evidence counts.
    """
    receipts = _receipts()
    events = [_receipt_event(r) for r in receipts]
    events.append(_score_event())
    events.extend(_forged_seal_events(receipts, agent="auditor-0"))

    result = _anchored(events)
    assert not result.passed, (
        "FORGERY ACCEPTED: fabricated seals attributed to the auditor graded PASS. "
        f"detail={result.detail!r}"
    )
