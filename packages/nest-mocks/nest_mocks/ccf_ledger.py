# SPDX-License-Identifier: Apache-2.0
"""LOCAL TEST-ONLY confidential ledger — TEST SERVICE IDENTITY, not production.

An in-memory stand-in for a CCF-based transparency service (Azure Confidential
Ledger): it appends a batch of application claims to a Merkle tree and mints
one CCF-shaped write receipt per claim — leaf components, inclusion proof, a
node certificate endorsed by the service identity, and an ECDSA signature over
the tree head — using **deterministic, publicly-derivable TEST keys**.

This exists so the discrimination tests can exercise the full offline
verification architecture — honest receipts PASS, forged / unsigned /
wrong-identity receipts FAIL — before the real ACL service identity is pinned.
Its security value is exactly zero by design:

* The service/node private keys are derived from fixed public strings, so
  *anyone* can mint receipts under them. That is fine **only** because the
  identity is never pinned: ``nest_core.ccf_receipt.PINNED_ACL_SERVICE_IDENTITY_PEM``
  must never be set to this certificate, and the validator only trusts it when
  a test explicitly injects it.
* Production receipts are minted by the real Azure Confidential Ledger at the
  operator-gated fixture step; nothing from this module may appear in the
  committed production fixtures.

Example::

    ledger = LocalTestConfidentialLedger()
    receipts = ledger.write_receipts([b"claim-0", b"claim-1"])
    assert verify_ccf_write_receipt(receipts[0], b"claim-0", ledger.service_identity_pem)
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ec import (
    ECDSA,
    SECP256R1,
    EllipticCurvePrivateKey,
    derive_private_key,
)
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509 import (
    BasicConstraints,
    Certificate,
    CertificateBuilder,
    Name,
    NameAttribute,
)
from cryptography.x509.oid import NameOID

#: Labels the deterministic TEST keys derive from. Publicly derivable on
#: purpose — these identities must NEVER be pinned as a production trust root.
TEST_SERVICE_LABEL = "TEST ACL SERVICE IDENTITY - not production"
#: A second, distinct test identity: receipts minted under it must FAIL
#: against the primary test identity (the wrong-identity discrimination case).
WRONG_SERVICE_LABEL = "WRONG ACL SERVICE IDENTITY - also not production"

#: Fixed validity window for the deterministic test certificates. The verifier
#: deliberately never reads a clock, so these bounds are cosmetic.
_NOT_BEFORE = datetime(2020, 1, 1, tzinfo=UTC)
_NOT_AFTER = datetime(2040, 1, 1, tzinfo=UTC)


def _derive_key(label: str) -> EllipticCurvePrivateKey:
    """Deterministic P-256 private key from a public label (test-only!)."""
    secret = int.from_bytes(hashlib.sha256(label.encode("utf-8")).digest(), "big")
    order = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
    return derive_private_key(secret % (order - 1) + 1, SECP256R1())


def _name(common_name: str) -> Name:
    return Name([NameAttribute(NameOID.COMMON_NAME, common_name)])


def _make_cert(
    subject: str,
    subject_key: EllipticCurvePrivateKey,
    issuer: str,
    issuer_key: EllipticCurvePrivateKey,
    *,
    serial: int,
    is_ca: bool,
) -> Certificate:
    return (
        CertificateBuilder()
        .subject_name(_name(subject))
        .issuer_name(_name(issuer))
        .public_key(subject_key.public_key())
        .serial_number(serial)
        .not_valid_before(_NOT_BEFORE)
        .not_valid_after(_NOT_AFTER)
        .add_extension(BasicConstraints(ca=is_ca, path_length=None), critical=True)
        .sign(issuer_key, SHA256())
    )


class LocalTestConfidentialLedger:
    """Mints CCF-shaped write receipts under a deterministic TEST service identity.

    The service identity is a self-signed CA certificate; receipts are signed
    by a node key whose certificate the service identity directly issues —
    mirroring how ACL write receipts carry a node cert endorsed by the
    service identity fetched from the ledger's identity endpoint.

    Example::

        ledger = LocalTestConfidentialLedger()
        [receipt] = ledger.write_receipts([b"hello"])
    """

    def __init__(self, service_label: str = TEST_SERVICE_LABEL) -> None:
        self._service_key = _derive_key(service_label)
        self._node_key = _derive_key(service_label + " / node 0")
        self._service_cert = _make_cert(
            service_label,
            self._service_key,
            service_label,
            self._service_key,
            serial=1,
            is_ca=True,
        )
        self._node_cert = _make_cert(
            service_label + " / node 0",
            self._node_key,
            service_label,
            self._service_key,
            serial=2,
            is_ca=False,
        )

    @property
    def service_identity_pem(self) -> str:
        """The service-identity certificate a test explicitly injects as pinned."""
        return self._service_cert.public_bytes(Encoding.PEM).decode("utf-8")

    def write_receipts(self, claims: list[bytes]) -> list[dict[str, Any]]:
        """Append ``claims`` to one tree; return one CCF-shaped write receipt each.

        Each receipt carries the leaf components for its claim
        (``claims_digest = SHA-256(claim)``), the inclusion proof to the tree
        head, the endorsed node certificate, and the node's ECDSA signature
        over the (prehashed) head.

        Example::

            receipts = ledger.write_receipts([b"a", b"b", b"c"])
        """
        if not claims:
            raise ValueError("empty batch has no tree head to sign")

        components: list[dict[str, str]] = []
        leaves: list[bytes] = []
        for i, claim in enumerate(claims):
            comp = {
                "write_set_digest": hashlib.sha256(b"ws:%d:" % i + claim).hexdigest(),
                "commit_evidence": f"ce:2.{i}:{hashlib.sha256(claim).hexdigest()[:16]}",
                "claims_digest": hashlib.sha256(claim).hexdigest(),
            }
            components.append(comp)
            leaves.append(
                hashlib.sha256(
                    bytes.fromhex(comp["write_set_digest"])
                    + hashlib.sha256(comp["commit_evidence"].encode("utf-8")).digest()
                    + bytes.fromhex(comp["claims_digest"])
                ).digest()
            )

        proofs: list[list[dict[str, str]]] = [[] for _ in leaves]
        indices = list(range(len(leaves)))
        level = list(leaves)
        while len(level) > 1:
            next_level: list[bytes] = []
            for pos in range(0, len(level) - 1, 2):
                next_level.append(hashlib.sha256(level[pos] + level[pos + 1]).digest())
            promoted = len(level) % 2 == 1
            if promoted:
                next_level.append(level[-1])
            for leaf_idx, pos in enumerate(indices):
                if promoted and pos == len(level) - 1:
                    indices[leaf_idx] = len(next_level) - 1
                    continue
                sibling = pos ^ 1
                side = "left" if sibling < pos else "right"
                proofs[leaf_idx].append({side: level[sibling].hex()})
                indices[leaf_idx] = pos // 2
            level = next_level

        root = level[0]
        signature = base64.b64encode(self._node_key.sign(root, ECDSA(Prehashed(SHA256())))).decode(
            "ascii"
        )
        node_pem = self._node_cert.public_bytes(Encoding.PEM).decode("utf-8")

        return [
            {
                "cert": node_pem,
                "leaf_components": components[i],
                "proof": proofs[i],
                "signature": signature,
            }
            for i in range(len(claims))
        ]


def receipt_bytes(receipt: dict[str, Any]) -> bytes:
    """Serialize a write receipt to the canonical bytes the fixture store holds.

    Example::

        blob = receipt_bytes(receipt)
    """
    return json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
