# SPDX-License-Identifier: Apache-2.0
"""capsule-emit-nanda — verifiable, anchored records for NANDA agents.

Two NANDA layer plugins:

- ``CapsuleEmitTrust`` (``trust: capsule_emit``) — drop-in for ``agent_receipts``
  that seals every interaction into an Agent Action Capsule ledger. Third-party
  verifiable via ``agent-action-capsule verify --store``.

- ``StripeCapsuledPayments`` (``payments: stripe_capsule``) — NANDA Payments layer
  that seals every completed payment into a capsule. Sandbox/mock by default
  (set ``STRIPE_SECRET_KEY`` for real payments).
"""
from capsule_emit_nanda.trust import CapsuleEmitTrust
from capsule_emit_nanda.payments import StripeCapsuledPayments

__all__ = ["CapsuleEmitTrust", "StripeCapsuledPayments"]
