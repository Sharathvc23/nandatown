# SPDX-License-Identifier: Apache-2.0
"""Conformance tests for the HTLC escrow payments plugin.

These tests exercise the trust-minimized payments properties:

* funds-locked-up-front (counterparty cannot abscond with un-delivered goods)
* hashlock atomicity (claim requires the preimage)
* timelock liveness (payer can always recover after expiry)
* conservation (total credits invariant across all operations)
* idempotent verify
* drop-in compat with the base ``Payments`` interface
"""

from __future__ import annotations

import hashlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from nest_core.types import (
    AgentId,
    Money,
    PaymentRef,
    PaymentStatus,
    Receipt,
    ServiceRef,
)
from nest_plugins_reference.payments.htlc_escrow import ESCROW_AGENT, HtlcEscrow

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_pair(
    buyer_start: int = 1000,
    seller_start: int = 0,
) -> tuple[HtlcEscrow, HtlcEscrow, dict[AgentId, int]]:
    """Create two HtlcEscrow handles over a shared ledger."""
    balances: dict[AgentId, int] = {
        AgentId("buyer"): buyer_start,
        AgentId("seller"): seller_start,
    }
    payments: dict[PaymentRef, Receipt] = {}
    contracts: dict[PaymentRef, object] = {}  # type: ignore[type-arg]
    clock: dict[str, int] = {"tick": 0}
    buyer = HtlcEscrow(
        AgentId("buyer"),
        initial_balance=0,
        balances=balances,
        payments=payments,
        contracts=contracts,  # type: ignore[arg-type]
        clock=clock,
    )
    seller = HtlcEscrow(
        AgentId("seller"),
        initial_balance=0,
        balances=balances,
        payments=payments,
        contracts=contracts,  # type: ignore[arg-type]
        clock=clock,
    )
    return buyer, seller, balances


def _total(balances: dict[AgentId, int]) -> int:
    return sum(balances.values())


# ---------------------------------------------------------------------------
# Happy-path HTLC: pay → claim
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pay_locks_funds_in_escrow() -> None:
    buyer, _, balances = _make_pair()
    _, lock = HtlcEscrow.make_secret(b"order-1")

    receipt = await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
        hashlock=lock,
        timelock_ticks=50,
    )

    # Payee not yet credited.
    assert receipt.payee == AgentId("seller")
    assert balances[AgentId("buyer")] == 900
    assert balances[AgentId("seller")] == 0
    assert balances[ESCROW_AGENT] == 100
    assert buyer.escrowed() == 100

    # Status is pending until claimed.
    assert await buyer.verify_payment(PaymentRef("p1")) == PaymentStatus.PENDING


@pytest.mark.asyncio
async def test_claim_releases_funds_to_payee() -> None:
    buyer, seller, balances = _make_pair()
    secret, lock = HtlcEscrow.make_secret(b"order-1")

    await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
        hashlock=lock,
        timelock_ticks=50,
    )
    receipt = await seller.claim(PaymentRef("p1"), secret)

    assert receipt.payer == AgentId("buyer")
    assert receipt.payee == AgentId("seller")
    assert balances[AgentId("buyer")] == 900
    assert balances[AgentId("seller")] == 100
    assert balances[ESCROW_AGENT] == 0
    assert await buyer.verify_payment(PaymentRef("p1")) == PaymentStatus.CONFIRMED


# ---------------------------------------------------------------------------
# Hashlock: wrong preimage rejected, double-claim rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_with_wrong_preimage_rejected() -> None:
    buyer, seller, balances = _make_pair()
    _, lock = HtlcEscrow.make_secret(b"order-1")

    await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
        hashlock=lock,
        timelock_ticks=50,
    )
    with pytest.raises(ValueError, match="Preimage does not match"):
        await seller.claim(PaymentRef("p1"), b"not-the-secret")

    # No state change.
    assert balances[AgentId("seller")] == 0
    assert balances[ESCROW_AGENT] == 100
    assert await seller.verify_payment(PaymentRef("p1")) == PaymentStatus.PENDING


@pytest.mark.asyncio
async def test_double_claim_rejected() -> None:
    buyer, seller, balances = _make_pair()
    secret, lock = HtlcEscrow.make_secret(b"order-1")

    await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
        hashlock=lock,
        timelock_ticks=50,
    )
    await seller.claim(PaymentRef("p1"), secret)
    with pytest.raises(ValueError, match="not claimable"):
        await seller.claim(PaymentRef("p1"), secret)
    assert balances[AgentId("seller")] == 100  # not doubled
    assert _total(balances) == 1000  # conservation


# ---------------------------------------------------------------------------
# Timelock: claim after expiry rejected, refund before expiry rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_after_timelock_rejected() -> None:
    buyer, seller, _ = _make_pair()
    secret, lock = HtlcEscrow.make_secret(b"order-1")

    await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
        hashlock=lock,
        timelock_ticks=10,
    )
    buyer.advance_clock(11)
    with pytest.raises(ValueError, match="Timelock expired"):
        await seller.claim(PaymentRef("p1"), secret)


@pytest.mark.asyncio
async def test_refund_before_timelock_rejected() -> None:
    buyer, _, _ = _make_pair()
    _, lock = HtlcEscrow.make_secret(b"order-1")

    await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
        hashlock=lock,
        timelock_ticks=50,
    )
    with pytest.raises(ValueError, match="Timelock not yet expired"):
        await buyer.refund_expired(PaymentRef("p1"))


@pytest.mark.asyncio
async def test_refund_after_timelock_returns_to_payer() -> None:
    buyer, _, balances = _make_pair()
    _, lock = HtlcEscrow.make_secret(b"order-1")

    await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
        hashlock=lock,
        timelock_ticks=10,
    )
    buyer.advance_clock(11)
    await buyer.refund_expired(PaymentRef("p1"))

    assert balances[AgentId("buyer")] == 1000
    assert balances[AgentId("seller")] == 0
    assert balances[ESCROW_AGENT] == 0
    assert await buyer.verify_payment(PaymentRef("p1")) == PaymentStatus.REFUNDED


# ---------------------------------------------------------------------------
# Adversarial: payee tries to drain after refund, payer tries to grief
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payee_cannot_claim_after_refund() -> None:
    """The classic double-spend attack: payer refunds, payee then tries to claim."""
    buyer, seller, balances = _make_pair()
    secret, lock = HtlcEscrow.make_secret(b"order-1")

    await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
        hashlock=lock,
        timelock_ticks=10,
    )
    buyer.advance_clock(11)
    await buyer.refund_expired(PaymentRef("p1"))

    with pytest.raises(ValueError, match="not claimable"):
        await seller.claim(PaymentRef("p1"), secret)

    assert _total(balances) == 1000  # conservation


@pytest.mark.asyncio
async def test_payer_cannot_refund_after_claim() -> None:
    """The mirror attack: payee claims first, payer tries to grief-refund."""
    buyer, seller, _ = _make_pair()
    secret, lock = HtlcEscrow.make_secret(b"order-1")

    await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
        hashlock=lock,
        timelock_ticks=10,
    )
    await seller.claim(PaymentRef("p1"), secret)
    buyer.advance_clock(20)

    with pytest.raises(ValueError, match="not refundable"):
        await buyer.refund_expired(PaymentRef("p1"))


@pytest.mark.asyncio
async def test_duplicate_payment_ref_rejected() -> None:
    buyer, _, _ = _make_pair()
    _, lock = HtlcEscrow.make_secret(b"order-1")
    await buyer.pay(
        AgentId("seller"),
        Money(amount=50),
        PaymentRef("p1"),
        hashlock=lock,
    )
    with pytest.raises(ValueError, match="Duplicate"):
        await buyer.pay(
            AgentId("seller"),
            Money(amount=50),
            PaymentRef("p1"),
            hashlock=lock,
        )


@pytest.mark.asyncio
async def test_self_pay_rejected() -> None:
    buyer, _, _ = _make_pair()
    _, lock = HtlcEscrow.make_secret(b"order-1")
    with pytest.raises(ValueError, match="Cannot escrow to self"):
        await buyer.pay(
            AgentId("buyer"),
            Money(amount=50),
            PaymentRef("p1"),
            hashlock=lock,
        )


@pytest.mark.asyncio
async def test_insufficient_balance_rejected_and_no_state_change() -> None:
    buyer, _, balances = _make_pair(buyer_start=10)
    _, lock = HtlcEscrow.make_secret(b"order-1")
    with pytest.raises(ValueError, match="Insufficient"):
        await buyer.pay(
            AgentId("seller"),
            Money(amount=50),
            PaymentRef("p1"),
            hashlock=lock,
        )
    assert balances[AgentId("buyer")] == 10
    assert balances[ESCROW_AGENT] == 0


@pytest.mark.asyncio
async def test_zero_amount_rejected() -> None:
    buyer, _, _ = _make_pair()
    _, lock = HtlcEscrow.make_secret(b"order-1")
    with pytest.raises(ValueError, match="positive"):
        await buyer.pay(
            AgentId("seller"),
            Money(amount=0),
            PaymentRef("p1"),
            hashlock=lock,
        )


@pytest.mark.asyncio
async def test_malformed_hashlock_rejected_atomically() -> None:
    buyer, _, balances = _make_pair()
    with pytest.raises(ValueError, match="32 bytes"):
        await buyer.pay(
            AgentId("seller"),
            Money(amount=100),
            PaymentRef("p1"),
            hashlock=b"short",
        )
    # Ledger must be untouched — atomic abort.
    assert balances[AgentId("buyer")] == 1000
    assert balances[ESCROW_AGENT] == 0
    assert buyer.get_contract(PaymentRef("p1")) is None


# ---------------------------------------------------------------------------
# Conservation invariant across mixed flows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conservation_across_multi_payment_mix() -> None:
    buyer, seller, balances = _make_pair(buyer_start=1000, seller_start=500)
    total_before = _total(balances)

    # Three payments: one claims, one refunds, one stays pending.
    s1, l1 = HtlcEscrow.make_secret(b"a")
    _, l2 = HtlcEscrow.make_secret(b"b")
    _, l3 = HtlcEscrow.make_secret(b"c")
    await buyer.pay(
        AgentId("seller"), Money(amount=100), PaymentRef("a"), hashlock=l1, timelock_ticks=100
    )
    await buyer.pay(
        AgentId("seller"), Money(amount=50), PaymentRef("b"), hashlock=l2, timelock_ticks=10
    )
    await buyer.pay(
        AgentId("seller"), Money(amount=25), PaymentRef("c"), hashlock=l3, timelock_ticks=1000
    )

    # Pending: 175 total locked.
    assert balances[ESCROW_AGENT] == 175
    assert _total(balances) == total_before  # invariant

    await seller.claim(PaymentRef("a"), s1)
    buyer.advance_clock(20)  # expires b but not c
    await buyer.refund_expired(PaymentRef("b"))

    assert balances[AgentId("buyer")] == 1000 - 100 - 25  # b refunded, c still locked
    assert balances[AgentId("seller")] == 500 + 100  # a claimed
    assert balances[ESCROW_AGENT] == 25  # c still pending
    assert _total(balances) == total_before  # conservation holds end-to-end


# ---------------------------------------------------------------------------
# Drop-in compatibility with the base Payments interface
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pay_without_hashlock_auto_settles_like_prepaid() -> None:
    """Calling pay() without a hashlock should behave like a direct transfer.

    Lets old protocols that don't speak HTLC still use this plugin.
    """
    buyer, _, balances = _make_pair()
    receipt = await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
    )
    assert receipt.payee == AgentId("seller")
    assert balances[AgentId("buyer")] == 900
    assert balances[AgentId("seller")] == 100
    assert balances[ESCROW_AGENT] == 0
    assert await buyer.verify_payment(PaymentRef("p1")) == PaymentStatus.CONFIRMED


@pytest.mark.asyncio
async def test_refund_after_auto_claim_reverses_transfer() -> None:
    buyer, _, balances = _make_pair()
    await buyer.pay(AgentId("seller"), Money(amount=100), PaymentRef("p1"))
    await buyer.refund(PaymentRef("p1"))
    assert balances[AgentId("buyer")] == 1000
    assert balances[AgentId("seller")] == 0


@pytest.mark.asyncio
async def test_refund_pending_uses_timelock() -> None:
    buyer, _, balances = _make_pair()
    _, lock = HtlcEscrow.make_secret(b"order-1")
    await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
        hashlock=lock,
        timelock_ticks=10,
    )
    # refund() before expiry refuses, even via the generic interface.
    with pytest.raises(ValueError, match="not yet expired"):
        await buyer.refund(PaymentRef("p1"))
    buyer.advance_clock(11)
    await buyer.refund(PaymentRef("p1"))
    assert balances[AgentId("buyer")] == 1000
    assert balances[ESCROW_AGENT] == 0


@pytest.mark.asyncio
async def test_refund_unknown_payment_rejected() -> None:
    buyer, _, _ = _make_pair()
    with pytest.raises(ValueError, match="not found"):
        await buyer.refund(PaymentRef("nope"))


@pytest.mark.asyncio
async def test_refund_already_refunded_rejected() -> None:
    buyer, _, _ = _make_pair()
    _, lock = HtlcEscrow.make_secret(b"order-1")
    await buyer.pay(
        AgentId("seller"),
        Money(amount=100),
        PaymentRef("p1"),
        hashlock=lock,
        timelock_ticks=10,
    )
    buyer.advance_clock(11)
    await buyer.refund(PaymentRef("p1"))
    with pytest.raises(ValueError, match="Already refunded"):
        await buyer.refund(PaymentRef("p1"))


@pytest.mark.asyncio
async def test_quote_matches_reference_default() -> None:
    pay = HtlcEscrow(AgentId("a1"))
    q = await pay.quote(ServiceRef("svc"))
    assert q.price.amount == 10


@pytest.mark.asyncio
async def test_verify_unknown_payment_returns_failed() -> None:
    pay = HtlcEscrow(AgentId("a1"))
    assert await pay.verify_payment(PaymentRef("nope")) == PaymentStatus.FAILED


# ---------------------------------------------------------------------------
# Determinism & helpers
# ---------------------------------------------------------------------------


def test_make_secret_deterministic_with_seed() -> None:
    s1, l1 = HtlcEscrow.make_secret(b"seed-1")
    s2, l2 = HtlcEscrow.make_secret(b"seed-1")
    s3, l3 = HtlcEscrow.make_secret(b"seed-2")
    assert s1 == s2 and l1 == l2
    assert s1 != s3 and l1 != l3
    # Hashlock is sha256 of preimage.
    assert l1 == hashlib.sha256(s1).digest()


def test_make_secret_random_when_unseeded() -> None:
    s1, l1 = HtlcEscrow.make_secret()
    s2, l2 = HtlcEscrow.make_secret()
    assert s1 != s2
    assert l1 != l2
    assert len(s1) == 32 and len(l1) == 32


def test_advance_clock_rejects_negative() -> None:
    pay = HtlcEscrow(AgentId("a1"))
    with pytest.raises(ValueError, match="rewind"):
        pay.advance_clock(-1)


def test_hashlock_of_matches_sha256() -> None:
    assert HtlcEscrow.hashlock_of(b"hello") == hashlib.sha256(b"hello").digest()


# ---------------------------------------------------------------------------
# Plugin registry resolution
# ---------------------------------------------------------------------------


def test_resolves_via_plugin_registry() -> None:
    from nest_core.plugins import PluginRegistry

    cls = PluginRegistry().resolve("payments", "htlc_escrow")
    assert cls is HtlcEscrow


# ---------------------------------------------------------------------------
# Property-based: conservation invariant under random op sequences
# ---------------------------------------------------------------------------


# 0 = pay, 1 = claim, 2 = refund_expired, 3 = advance_clock
_OP = st.integers(min_value=0, max_value=3)


@settings(max_examples=80, deadline=None)
@given(
    ops=st.lists(
        st.tuples(_OP, st.integers(min_value=1, max_value=200)),
        min_size=1,
        max_size=40,
    ),
    starting_balance=st.integers(min_value=0, max_value=5000),
)
@pytest.mark.asyncio
async def test_conservation_under_random_op_sequence(
    ops: list[tuple[int, int]],
    starting_balance: int,
) -> None:
    """Sum of all balances (incl. escrow) is invariant under ANY op sequence.

    This is the property that, if it fails, money is being printed or
    destroyed.  Coinbase-grade ledger code lives or dies on this one.
    """
    buyer, seller, balances = _make_pair(buyer_start=starting_balance)
    total_before = _total(balances)

    # Track outstanding refs and their secrets so claim/refund have something
    # to act on.  This is fine — we want to exercise legal *and* illegal
    # transitions; both should leave conservation intact.
    pending: list[tuple[PaymentRef, bytes]] = []
    counter = 0

    for op, arg in ops:
        try:
            if op == 0:  # pay
                counter += 1
                ref = PaymentRef(f"p{counter}")
                secret, lock = HtlcEscrow.make_secret(ref.encode())
                amount = (arg % 200) + 1
                await buyer.pay(
                    AgentId("seller"),
                    Money(amount=amount),
                    ref,
                    hashlock=lock,
                    timelock_ticks=(arg % 50) + 1,
                )
                pending.append((ref, secret))
            elif op == 1 and pending:  # claim
                idx = arg % len(pending)
                ref, secret = pending[idx]
                await seller.claim(ref, secret)
            elif op == 2 and pending:  # refund_expired
                idx = arg % len(pending)
                ref, _ = pending[idx]
                await buyer.refund_expired(ref)
            elif op == 3:  # advance clock
                buyer.advance_clock(arg % 20)
        except ValueError:
            # Illegal transitions raise; that's *expected* — what we care
            # about is that they don't corrupt the ledger.
            pass

        # Invariant — checked after EVERY op, even the failing ones.
        assert _total(balances) == total_before, (
            f"Conservation violated after op={op}, arg={arg}; balances={balances}"
        )
        # And escrow never goes negative.
        assert balances[ESCROW_AGENT] >= 0
        for aid in (AgentId("buyer"), AgentId("seller")):
            assert balances[aid] >= 0


@settings(max_examples=50, deadline=None)
@given(
    amount=st.integers(min_value=1, max_value=1000),
    expiry=st.integers(min_value=1, max_value=100),
    expire_first=st.booleans(),
)
@pytest.mark.asyncio
async def test_exactly_one_terminal_state(
    amount: int,
    expiry: int,
    expire_first: bool,
) -> None:
    """Any HTLC reaches *exactly one* of CONFIRMED or REFUNDED — never both."""
    buyer, seller, _ = _make_pair(buyer_start=10_000)
    secret, lock = HtlcEscrow.make_secret(b"order")
    await buyer.pay(
        AgentId("seller"),
        Money(amount=amount),
        PaymentRef("p"),
        hashlock=lock,
        timelock_ticks=expiry,
    )

    if expire_first:
        buyer.advance_clock(expiry + 1)
        await buyer.refund_expired(PaymentRef("p"))
        status = await buyer.verify_payment(PaymentRef("p"))
        assert status == PaymentStatus.REFUNDED
        # Cannot also claim.
        with pytest.raises(ValueError):
            await seller.claim(PaymentRef("p"), secret)
    else:
        await seller.claim(PaymentRef("p"), secret)
        status = await buyer.verify_payment(PaymentRef("p"))
        assert status == PaymentStatus.CONFIRMED
        # Cannot also refund.
        buyer.advance_clock(expiry + 1)
        with pytest.raises(ValueError):
            await buyer.refund_expired(PaymentRef("p"))
