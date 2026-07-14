# SPDX-License-Identifier: Apache-2.0
"""Vendored, pure-Python CCF write-receipt verifier — the anchoring root of trust.

The anchoring gate's evidence is a **verifiable CCF / Azure Confidential
Ledger (ACL) write receipt**: a Merkle inclusion proof from the registered
claim to the ledger's tree head, plus an ECDSA signature over that head made
by the ledger's **service identity** — an independent transparency service
whose private key the participant does NOT hold. The validator verifies the
receipt OFFLINE against a *pinned* service-identity certificate; forging one
requires the ledger's signing key, so the evidence cannot be fabricated from
plaintext trace content.

(Precision note: this is the CCF-native write-receipt format ACL emits at its
data-plane ``ledgerUri`` — deliberately NOT an RFC 9942 / SCITT COSE receipt
parser. We claim exactly what we verify.)

Everything here is vendored and fail-closed, in the same discipline as
``nest_core.canonical``: no network, no filesystem, no environment, no clock,
no external packages beyond ``cryptography`` (already a nest-core dependency).
Every malformed, truncated, wrong-key, or wrong-claim input yields ``False``
from :func:`verify_ccf_write_receipt` — never a crash, never a default-open
path.

Receipt shape (the JSON subset of a CCF/ACL write receipt this verifier
consumes; see the CCF receipt-verification reference and ``pyscitt`` as prior
art)::

    {
      "cert": "<PEM: the signing node's certificate>",
      "leaf_components": {
        "write_set_digest": "<hex sha-256>",
        "commit_evidence": "<string>",
        "claims_digest": "<hex sha-256 of the application claim>"
      },
      "proof": [{"left": "<hex>"} | {"right": "<hex>"}, ...],
      "signature": "<base64 DER ECDSA over the 32-byte root, prehashed>"
    }

Verification, exactly as CCF specifies:

1. The application claim binds the statement: ``claims_digest`` must equal
   ``SHA-256(statement)``.
2. ``leaf = SHA-256(write_set_digest ‖ SHA-256(commit_evidence) ‖ claims_digest)``.
3. Fold the proof: ``left``  steps prepend (``SHA-256(step ‖ acc)``), ``right``
   steps append (``SHA-256(acc ‖ step)``); the result is the tree head.
4. The node certificate in ``cert`` must be directly issued (and signed) by
   the pinned service-identity certificate — or be that certificate itself.
5. The ECDSA signature must verify over the (prehashed SHA-256) tree head
   under the node certificate's public key.

Certificate *time* validity is deliberately not evaluated: the verdict path
reads no clock (determinism), and the root of trust is the pinned key itself,
established once at the operator-gated setup step.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ec import ECDSA, EllipticCurvePublicKey
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.x509 import Certificate, load_pem_x509_certificate

#: The pinned service identity of the production transparency service (the
#: Azure Confidential Ledger instance), as a PEM certificate string.
#:
#: TODO(operator-gated fixture step): pin the real ACL service-identity
#: certificate here — fetched ONCE at setup from the ACL identity endpoint for
#: the confirmed ``ledgerUri`` — alongside committing the pre-obtained write-
#: receipt fixtures. ``None`` means *no identity is pinned yet*, and the
#: validator fails closed: no anchoring evidence can verify, so every trace
#: grades FAIL on the anchored check. This placeholder can only ever reject —
#: it cannot be used to smuggle a PASS.
PINNED_ACL_SERVICE_IDENTITY_PEM: str | None = None


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _hex32(value: Any) -> bytes:
    """Decode a 64-char lowercase-hex SHA-256 string; raise ``ValueError`` otherwise."""
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("expected a 64-character hex digest")
    return bytes.fromhex(value)


def _leaf_from_components(components: Any) -> bytes:
    """CCF leaf hash: ``SHA-256(write_set_digest ‖ SHA-256(commit_evidence) ‖ claims_digest)``."""
    if not isinstance(components, dict):
        raise ValueError("leaf_components must be an object")
    comp = cast("dict[str, Any]", components)
    write_set_digest = _hex32(comp.get("write_set_digest"))
    commit_evidence = comp.get("commit_evidence")
    if not isinstance(commit_evidence, str) or not commit_evidence:
        raise ValueError("commit_evidence must be a non-empty string")
    claims_digest = _hex32(comp.get("claims_digest"))
    return _sha256(write_set_digest + _sha256(commit_evidence.encode("utf-8")) + claims_digest)


def _root_from_proof(leaf: bytes, proof: Any) -> bytes:
    """Fold the CCF inclusion proof from ``leaf`` to the signed tree head."""
    if not isinstance(proof, list):
        raise ValueError("proof must be a list")
    acc = leaf
    for step in cast("list[Any]", proof):
        if not isinstance(step, dict) or len(cast("dict[str, Any]", step)) != 1:
            raise ValueError("each proof step must be a single left/right object")
        step_map = cast("dict[str, Any]", step)
        if "left" in step_map:
            acc = _sha256(_hex32(step_map["left"]) + acc)
        elif "right" in step_map:
            acc = _sha256(acc + _hex32(step_map["right"]))
        else:
            raise ValueError("proof step is neither left nor right")
    return acc


def _endorsed_node_certificate(cert_pem: Any, service_identity_pem: str) -> Certificate:
    """Return the signing node certificate iff the pinned service identity endorses it.

    Accepts either the service-identity certificate itself or a node
    certificate directly issued *and signed* by it. Raises on anything else.
    """
    if not isinstance(cert_pem, str):
        raise ValueError("receipt cert must be a PEM string")
    node_cert = load_pem_x509_certificate(cert_pem.encode("utf-8"))
    service_cert = load_pem_x509_certificate(service_identity_pem.encode("utf-8"))
    if node_cert == service_cert:
        return node_cert
    # Issuer/subject linkage + the service identity's signature over the node cert.
    node_cert.verify_directly_issued_by(service_cert)
    return node_cert


def verify_ccf_write_receipt(
    receipt: dict[str, Any], statement: bytes, service_identity_pem: str
) -> bool:
    """Verify a CCF/ACL write receipt binds ``statement`` under the pinned identity.

    ``True`` only when every layer checks out: the claim digest matches the
    statement, the Merkle proof folds from that claim's leaf to the tree head,
    the signing node certificate is endorsed by the pinned service identity,
    and the service's ECDSA signature verifies over that head. Never raises.
    Zero network, filesystem, environment, or clock access.

    Example::

        ok = verify_ccf_write_receipt(receipt, bytes.fromhex(digest), pinned_pem)
    """
    try:
        components = receipt.get("leaf_components")
        if not isinstance(components, dict):
            return False
        claims_digest = _hex32(cast("dict[str, Any]", components).get("claims_digest"))
        if claims_digest != _sha256(statement):
            return False

        root = _root_from_proof(_leaf_from_components(components), receipt.get("proof"))

        signature_b64 = receipt.get("signature")
        if not isinstance(signature_b64, str):
            return False
        signature = base64.b64decode(signature_b64, validate=True)

        node_cert = _endorsed_node_certificate(receipt.get("cert"), service_identity_pem)
        public_key = node_cert.public_key()
        if not isinstance(public_key, EllipticCurvePublicKey):
            return False
        public_key.verify(signature, root, ECDSA(Prehashed(SHA256())))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
