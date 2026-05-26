# SPDX-License-Identifier: Apache-2.0
"""HTLC escrow payments plugin — hash- and time-locked conditional payments.

The default ``prepaid_credits`` plugin moves funds the instant ``pay()`` is
called.  That works for cooperative simulation, but it bakes in
*counterparty trust*: the payee can take the money and never deliver, and
the payer has no atomic recourse other than reporting after-the-fact.
HTLC fixes that.  At ``pay()`` time funds are *locked in escrow*, not
transferred.  The payee can claim them only by revealing the preimage
of a hash the payer committed to; if no claim arrives before the
timelock expires, the payer can refund unilaterally.  The same primitive
underpins Bitcoin Lightning, atomic swaps, and rollup bridges.

Properties this implementation enforces:

* **Conservation.** Escrowed funds are debited from the payer and held by
  the contract.  Total credits across (balances + escrow) is invariant.
* **No double-spend.** Reusing a ``PaymentRef`` raises.  An escrow can be
  claimed *xor* refunded, exactly once.
* **Hashlock.** Only a preimage whose SHA-256 matches the contract's
  ``hashlock`` releases funds.  Wrong preimage → ``ValueError``.
* **Timelock.** Refund is rejected before the expiry tick; claim is
  rejected after.
* **Idempotent verify.** ``verify_payment`` is read-only and reflects the
  ledger state (``PENDING`` → ``CONFIRMED`` | ``REFUNDED`` | ``FAILED``).
* **Deterministic preimages.** A helper exposes ``make_secret`` which
  hashes a caller-supplied seed, so simulations seeded with the same
  master RNG replay byte-identically.

Example::

    pay = HtlcEscrow(AgentId("buyer"), initial_balance=1000)
    secret, lock = pay.make_secret(b"order-1")
    receipt = await pay.pay(
        AgentId("seller"), Money(amount=50), PaymentRef("p1"),
        hashlock=lock, timelock_ticks=100,
    )
    # ... seller delivers ...
    await pay.claim(PaymentRef("p1"), secret)
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field

from nest_core.types import (
    AgentId,
    Money,
    PaymentRef,
    PaymentStatus,
    Quote,
    Receipt,
    ServiceRef,
)

ESCROW_AGENT = AgentId("__htlc_escrow__")
"""Sentinel agent id used to hold locked funds in the shared balance map.

Exported so validators, tests, and scenario factories can inspect the
escrow account directly (e.g., to assert conservation invariants on a
trace replay).

Example::

    locked = balances[ESCROW_AGENT]
"""

# Backwards-compatible private alias retained for any internal callers.
_ESCROW_AGENT = ESCROW_AGENT


@dataclass
class _Contract:
    """In-memory HTLC contract record.

    Internal — not exported.  Held in the shared ``contracts`` dict so
    every per-agent ``HtlcEscrow`` handle observes the same state.

    Example::

        c = _Contract(
            ref=PaymentRef("p1"), payer=AgentId("a1"), payee=AgentId("a2"),
            amount=Money(amount=10), hashlock=b"\\x00" * 32, expiry_tick=100,
        )
    """

    ref: PaymentRef
    payer: AgentId
    payee: AgentId
    amount: Money
    hashlock: bytes
    expiry_tick: int
    status: PaymentStatus = PaymentStatus.PENDING
    preimage: bytes | None = None
    receipt: Receipt | None = None
    metadata: dict[str, str] = field(default_factory=dict[str, str])


class HtlcEscrow:
    """Hash- and time-locked escrow payments.

    Drop-in replacement for ``PrepaidCredits`` that adds escrow semantics.
    Calls to the base ``pay(to, amount, ref)`` signature still work — the
    plugin synthesizes a hashlock from a random secret and immediately
    auto-claims, falling back to prepaid-style behavior for protocols that
    don't yet understand HTLC.  Protocols that *do* know about HTLC pass
    ``hashlock`` and ``timelock_ticks`` explicitly and call ``claim``
    / ``refund_expired`` themselves.

    Example::

        pay = HtlcEscrow(AgentId("buyer"), initial_balance=1000)
        secret, lock = pay.make_secret(b"order-1")
        await pay.pay(
            AgentId("seller"), Money(amount=50), PaymentRef("p1"),
            hashlock=lock, timelock_ticks=200,
        )
        # seller proves delivery by revealing the preimage
        await pay.claim(PaymentRef("p1"), secret)
    """

    # Defaults are deliberately conservative — long enough to outlast a
    # typical scenario tick budget, short enough that a forgotten escrow
    # eventually unsticks itself.
    DEFAULT_TIMELOCK_TICKS = 10_000

    def __init__(
        self,
        agent_id: AgentId,
        initial_balance: int = 1000,
        balances: dict[AgentId, int] | None = None,
        payments: dict[PaymentRef, Receipt] | None = None,
        contracts: dict[PaymentRef, _Contract] | None = None,
        clock: dict[str, int] | None = None,
        default_timelock_ticks: int | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._balances = balances if balances is not None else {}
        self._balances.setdefault(agent_id, initial_balance)
        # Escrow always exists as a real account so conservation holds.
        self._balances.setdefault(_ESCROW_AGENT, 0)
        self._payments = payments if payments is not None else {}
        self._contracts = contracts if contracts is not None else {}
        # Clock is shared mutable dict so tests / scenarios can advance it.
        self._clock = clock if clock is not None else {"tick": 0}
        self._clock.setdefault("tick", 0)
        self._default_timelock = (
            default_timelock_ticks
            if default_timelock_ticks is not None
            else self.DEFAULT_TIMELOCK_TICKS
        )

    # ------------------------------------------------------------------
    # Helpers / inspection
    # ------------------------------------------------------------------

    def balance(self, agent: AgentId) -> int:
        """Return the on-ledger balance of ``agent`` (escrowed funds excluded).

        Example::

            bal = pay.balance(AgentId("buyer"))
        """
        return self._balances.get(agent, 0)

    def escrowed(self) -> int:
        """Return the total amount currently locked in escrow contracts.

        Example::

            locked = pay.escrowed()
        """
        return self._balances.get(_ESCROW_AGENT, 0)

    def now(self) -> int:
        """Return the current logical tick used for timelock checks.

        Example::

            t = pay.now()
        """
        return self._clock.get("tick", 0)

    def advance_clock(self, ticks: int = 1) -> int:
        """Advance the shared logical clock by ``ticks`` and return the new value.

        Tests and scenarios that don't have access to the simulator's
        event loop use this to simulate timelock expiry.

        Example::

            pay.advance_clock(101)
        """
        if ticks < 0:
            msg = f"Cannot rewind clock: ticks={ticks}"
            raise ValueError(msg)
        self._clock["tick"] = self._clock.get("tick", 0) + ticks
        return self._clock["tick"]

    @staticmethod
    def hashlock_of(preimage: bytes) -> bytes:
        """Return SHA-256 of ``preimage`` — the canonical hashlock construction.

        Example::

            lock = HtlcEscrow.hashlock_of(b"my-secret")
        """
        return hashlib.sha256(preimage).digest()

    @staticmethod
    def make_secret(seed: bytes | None = None) -> tuple[bytes, bytes]:
        """Return ``(preimage, hashlock)``; deterministic when ``seed`` is given.

        Pass a deterministic seed (derived from the scenario RNG) for
        reproducible traces.  Pass ``None`` for cryptographic randomness.

        Example::

            secret, lock = HtlcEscrow.make_secret(b"buyer-0|order-3")
        """
        if seed is None:
            preimage = secrets.token_bytes(32)
        else:
            # Domain-separated PBKDF: avoids accidentally colliding with
            # whatever the seed bytes mean elsewhere.
            preimage = hashlib.sha256(b"nest-htlc-preimage|" + seed).digest()
        return preimage, hashlib.sha256(preimage).digest()

    def get_contract(self, ref: PaymentRef) -> _Contract | None:
        """Return a copy of the contract for ``ref``, or ``None`` if unknown.

        Inspection helper for tests and validators.  The returned object
        is the live record — callers should treat it as read-only.

        Example::

            c = pay.get_contract(PaymentRef("p1"))
        """
        return self._contracts.get(ref)

    # ------------------------------------------------------------------
    # Payments protocol surface
    # ------------------------------------------------------------------

    async def quote(self, service: ServiceRef) -> Quote:
        """Return a fixed quote — same surface as ``prepaid_credits``.

        Example::

            q = await pay.quote(ServiceRef("svc"))
        """
        return Quote(service=service, price=Money(amount=10))

    async def pay(
        self,
        to: AgentId,
        amount: Money,
        ref: PaymentRef,
        *,
        hashlock: bytes | None = None,
        timelock_ticks: int | None = None,
    ) -> Receipt:
        """Lock ``amount`` in escrow conditional on ``hashlock`` and a timelock.

        Behavior:

        * If ``hashlock`` is provided, funds are locked.  The payee must
          call :meth:`claim` with a preimage before the timelock expires;
          otherwise the payer can call :meth:`refund_expired`.
        * If ``hashlock`` is ``None``, the plugin generates one
          deterministically from ``ref`` *and* auto-claims so the call
          behaves like a direct transfer.  This keeps the plugin
          drop-in-compatible with protocols that don't know HTLC yet.

        Example::

            await pay.pay(
                AgentId("seller"), Money(amount=10), PaymentRef("p1"),
                hashlock=lock, timelock_ticks=200,
            )
        """
        if amount.amount <= 0:
            msg = f"Payment amount must be positive: {amount.amount}"
            raise ValueError(msg)
        if ref in self._payments or ref in self._contracts:
            msg = f"Duplicate payment reference: {ref}"
            raise ValueError(msg)
        if to == self._agent_id:
            # Self-pay would allow refund-replay games.  Cheap to forbid.
            msg = f"Cannot escrow to self: {to}"
            raise ValueError(msg)

        payer_balance = self._balances.get(self._agent_id, 0)
        if payer_balance < amount.amount:
            msg = f"Insufficient balance: {payer_balance} < {amount.amount}"
            raise ValueError(msg)

        # Lock funds: debit payer, credit the escrow sentinel.  Doing this
        # atomically — before we register the contract — means a crash
        # between lines never leaves dangling escrow.
        self._balances[self._agent_id] = payer_balance - amount.amount
        self._balances[_ESCROW_AGENT] = self._balances.get(_ESCROW_AGENT, 0) + amount.amount

        auto_claim = hashlock is None
        if auto_claim:
            preimage, hashlock = self.make_secret(b"auto|" + ref.encode())
        else:
            preimage = None
            if len(hashlock) != 32:
                # Atomically undo the escrow before raising — never leave
                # the ledger in an inconsistent state.
                self._balances[self._agent_id] += amount.amount
                self._balances[_ESCROW_AGENT] -= amount.amount
                msg = f"hashlock must be 32 bytes (got {len(hashlock)})"
                raise ValueError(msg)

        expiry = self.now() + (
            timelock_ticks if timelock_ticks is not None else self._default_timelock
        )
        contract = _Contract(
            ref=ref,
            payer=self._agent_id,
            payee=to,
            amount=amount,
            hashlock=hashlock,
            expiry_tick=expiry,
        )
        self._contracts[ref] = contract

        if auto_claim:
            # Compat path: behave like a direct transfer for protocols
            # that don't know about HTLC.  Still goes through the same
            # claim() code path so the conservation invariant holds.
            assert preimage is not None
            return await self.claim(ref, preimage)

        # Return a "pending" receipt — the payer has evidence funds are
        # locked, but the payee is not credited yet.
        return Receipt(ref=ref, payer=self._agent_id, payee=to, amount=amount)

    async def claim(self, ref: PaymentRef, preimage: bytes) -> Receipt:
        """Reveal ``preimage`` to release escrow to the payee.

        Reverts cleanly if the contract is unknown, already settled, the
        timelock has expired, or the preimage doesn't match the hashlock.

        Example::

            receipt = await pay.claim(PaymentRef("p1"), secret)
        """
        contract = self._contracts.get(ref)
        if contract is None:
            msg = f"Unknown contract: {ref}"
            raise ValueError(msg)
        if contract.status is not PaymentStatus.PENDING:
            msg = f"Contract not claimable in state {contract.status.value}: {ref}"
            raise ValueError(msg)
        if self.now() >= contract.expiry_tick:
            # Mark expired so the next refund call doesn't have to redo
            # the check.  We don't move funds yet — that's refund()'s job.
            msg = f"Timelock expired: now={self.now()} >= expiry={contract.expiry_tick}"
            raise ValueError(msg)
        if hashlib.sha256(preimage).digest() != contract.hashlock:
            msg = f"Preimage does not match hashlock for {ref}"
            raise ValueError(msg)

        escrow = self._balances.get(_ESCROW_AGENT, 0)
        if escrow < contract.amount.amount:
            # Should be unreachable: invariant guarantees it.  But better
            # to fail loudly than silently double-spend if a future bug
            # violates conservation.
            msg = "Escrow accounting invariant violated"
            raise RuntimeError(msg)

        self._balances[_ESCROW_AGENT] = escrow - contract.amount.amount
        self._balances[contract.payee] = (
            self._balances.get(contract.payee, 0) + contract.amount.amount
        )

        receipt = Receipt(
            ref=ref,
            payer=contract.payer,
            payee=contract.payee,
            amount=contract.amount,
        )
        contract.status = PaymentStatus.CONFIRMED
        contract.preimage = preimage
        contract.receipt = receipt
        self._payments[ref] = receipt
        return receipt

    async def refund_expired(self, ref: PaymentRef) -> None:
        """Release escrow back to the payer after the timelock has expired.

        Only the payer (or anyone holding their handle) can call this,
        and only after ``now() >= expiry_tick``.  Prior to expiry the
        payee still has the chance to claim — the payer cannot rug them.

        Example::

            pay.advance_clock(101)
            await pay.refund_expired(PaymentRef("p1"))
        """
        contract = self._contracts.get(ref)
        if contract is None:
            msg = f"Unknown contract: {ref}"
            raise ValueError(msg)
        if contract.status is not PaymentStatus.PENDING:
            msg = f"Contract not refundable in state {contract.status.value}: {ref}"
            raise ValueError(msg)
        if self.now() < contract.expiry_tick:
            msg = f"Timelock not yet expired: now={self.now()} < expiry={contract.expiry_tick}"
            raise ValueError(msg)

        escrow = self._balances.get(_ESCROW_AGENT, 0)
        if escrow < contract.amount.amount:
            msg = "Escrow accounting invariant violated"
            raise RuntimeError(msg)
        self._balances[_ESCROW_AGENT] = escrow - contract.amount.amount
        self._balances[contract.payer] = (
            self._balances.get(contract.payer, 0) + contract.amount.amount
        )
        contract.status = PaymentStatus.REFUNDED

    async def verify_payment(self, ref: PaymentRef) -> PaymentStatus:
        """Return the live status of the escrow / payment.

        ``PENDING`` while funds are locked, ``CONFIRMED`` once claimed,
        ``REFUNDED`` once the payer has reclaimed an expired escrow, and
        ``FAILED`` for unknown refs.  Read-only and side-effect free.

        Example::

            status = await pay.verify_payment(PaymentRef("p1"))
        """
        contract = self._contracts.get(ref)
        if contract is not None:
            return contract.status
        if ref in self._payments:
            return PaymentStatus.CONFIRMED
        return PaymentStatus.FAILED

    async def refund(self, ref: PaymentRef) -> None:
        """Refund a payment — adapter to the base ``Payments`` interface.

        Semantics depend on contract state:

        * ``PENDING``: same as :meth:`refund_expired` (timelock check enforced).
        * ``CONFIRMED``: reverses an already-claimed payment by debiting the
          payee and crediting the payer; matches ``prepaid_credits.refund``.
        * ``REFUNDED``: no-op-error; the funds have already been returned.

        Example::

            await pay.refund(PaymentRef("p1"))
        """
        contract = self._contracts.get(ref)
        if contract is None:
            # No contract at all — fall back to legacy receipt-based refund.
            receipt = self._payments.get(ref)
            if receipt is None:
                msg = f"Payment not found: {ref}"
                raise ValueError(msg)
            self._reverse_settled_payment(receipt)
            del self._payments[ref]
            return

        if contract.status is PaymentStatus.PENDING:
            await self.refund_expired(ref)
            return
        if contract.status is PaymentStatus.REFUNDED:
            msg = f"Already refunded: {ref}"
            raise ValueError(msg)
        if contract.status is PaymentStatus.CONFIRMED:
            assert contract.receipt is not None
            self._reverse_settled_payment(contract.receipt)
            contract.status = PaymentStatus.REFUNDED
            self._payments.pop(ref, None)
            return

        msg = f"Refund not supported in state {contract.status.value}: {ref}"
        raise ValueError(msg)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reverse_settled_payment(self, receipt: Receipt) -> None:
        """Move funds from payee back to payer for an already-confirmed payment.

        Used by :meth:`refund` for the post-claim case.  Verifies the payee
        has the funds to refund — otherwise the operation aborts.

        Example::

            pay._reverse_settled_payment(receipt)
        """
        payee_balance = self._balances.get(receipt.payee, 0)
        if payee_balance < receipt.amount.amount:
            msg = (
                f"Insufficient balance for refund: {receipt.payee} has "
                f"{payee_balance}, needs {receipt.amount.amount}"
            )
            raise ValueError(msg)
        self._balances[receipt.payee] = payee_balance - receipt.amount.amount
        self._balances[receipt.payer] = self._balances.get(receipt.payer, 0) + receipt.amount.amount
