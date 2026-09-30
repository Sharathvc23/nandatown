"""Exact versioned path profiles: executable integration contracts.

A path profile names what is being tested, the exact request, the
expected observable result, the controlled condition, and the limits.
It is frozen and fingerprinted; a result binds to the exact profile
version it ran under. These fixtures are Town-authored integration
tests, not universal commerce standards.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .records import fingerprint

PATH_EVALUATOR = "path-evaluator@0.1"
STRICT_PATH_EVALUATOR = "path-evaluator@0.2"
QUOTE_INTENT_EVALUATOR = "quote-intent-evaluator@0.1"
STRICT_QUOTE_INTENT_EVALUATOR = "quote-intent-evaluator@0.2"
QUOTE_INTENT_FIELDS = ("sku", "color", "quantity", "merchant_id", "currency")


class PathProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile_id: str
    version: str
    protocol: Literal["a2a"]
    capability: str
    request: dict[str, Any]
    expected: dict[str, Any]
    controlled_condition: Literal["duplicate_request"]
    limits: dict[str, float]
    evaluator: str

    @property
    def ref(self) -> str:
        return f"{self.profile_id}@{self.version}"

    def fingerprint(self) -> str:
        return fingerprint(self.model_dump())


PATH_PROFILES: dict[str, PathProfile] = {
    "a2a-quote-intent@0.1": PathProfile(
        profile_id="a2a-quote-intent",
        version="0.1",
        protocol="a2a",
        capability="quote",
        request={"sku": "widget", "quantity": 2, "unit_price_cents": 1995,
                 "color": "blue", "merchant_id": "town-reference", "currency": "USD"},
        expected={"max_total_cents": 3990,
                  "quote": {"sku": "widget", "quantity": 2, "color": "blue",
                            "merchant_id": "town-reference", "currency": "USD"}},
        controlled_condition="duplicate_request",
        limits={"timeout_seconds": 15.0, "max_response_bytes": 1_048_576},
        evaluator=QUOTE_INTENT_EVALUATOR,
    ),
    "a2a-quote-intent@0.2": PathProfile(
        profile_id="a2a-quote-intent",
        version="0.2",
        protocol="a2a",
        capability="quote",
        request={"sku": "widget", "quantity": 2, "unit_price_cents": 1995,
                 "color": "blue", "merchant_id": "town-reference",
                 "currency": "USD"},
        expected={"max_total_cents": 3990, "terminal_fulfillments": 1,
                  "quote": {"sku": "widget", "quantity": 2,
                            "color": "blue",
                            "merchant_id": "town-reference",
                            "currency": "USD"}},
        controlled_condition="duplicate_request",
        limits={"timeout_seconds": 15.0,
                "max_response_bytes": 1_048_576},
        evaluator=STRICT_QUOTE_INTENT_EVALUATOR,
    ),
    "a2a-capability-fulfillment@0.1": PathProfile(
        profile_id="a2a-capability-fulfillment",
        version="0.1",
        protocol="a2a",
        capability="quote",
        request={"sku": "widget", "quantity": 2,
                 "unit_price_cents": 1995},
        expected={"total_cents": 3990, "terminal_fulfillments": 1},
        controlled_condition="duplicate_request",
        limits={"timeout_seconds": 15.0},
        evaluator=PATH_EVALUATOR,
    ),
    "a2a-capability-fulfillment@0.2": PathProfile(
        profile_id="a2a-capability-fulfillment",
        version="0.2",
        protocol="a2a",
        capability="quote",
        request={"sku": "widget", "quantity": 2,
                 "unit_price_cents": 1995},
        expected={"total_cents": 3990, "terminal_fulfillments": 1},
        controlled_condition="duplicate_request",
        limits={"timeout_seconds": 15.0, "max_response_bytes": 1_048_576},
        evaluator=PATH_EVALUATOR,
    ),
    "a2a-capability-fulfillment@0.3": PathProfile(
        profile_id="a2a-capability-fulfillment",
        version="0.3",
        protocol="a2a",
        capability="quote",
        request={"sku": "widget", "quantity": 2,
                 "unit_price_cents": 1995},
        expected={"total_cents": 3990, "terminal_fulfillments": 1},
        controlled_condition="duplicate_request",
        limits={"timeout_seconds": 15.0,
                "max_response_bytes": 1_048_576},
        evaluator=STRICT_PATH_EVALUATOR,
    ),
    # An A2A booking, judged on the fields the profile names rather than on a
    # price. Its controlled condition is the invariant the capability turns on:
    # a slot is an idempotency key, so the identical intent delivered twice must
    # return the same booking and not a second one. `state: held` is what one
    # principal's request produces when the booking names two — a booking with
    # one signature is not joint consent, and a profile that expected
    # `confirmed` here would be asserting the opposite of the property.
    "a2a-booking-intent@0.1": PathProfile(
        profile_id="a2a-booking-intent",
        version="0.1",
        protocol="a2a",
        capability="booking",
        request={"skill": "venue.hold",
                 "resource": "town-reference-table",
                 "start": "2026-12-24T19:00:00Z",
                 "party": "did:key:z6MkjTownReferenceBuyerAAAAAAAAAAAAAAAAAAAAAA",
                 "principals": ["did:key:z6MkjTownReferenceBuyerAAAAAAAAAAAAAAAAAAAAAA",
                                "did:key:z6MkjTownReferenceHostBBBBBBBBBBBBBBBBBBBBBB"]},
        expected={"fields": {"resource": "town-reference-table",
                             "start": "2026-12-24T19:00:00Z",
                             "state": "held"},
                  "terminal_fulfillments": 1},
        controlled_condition="duplicate_request",
        limits={"timeout_seconds": 15.0, "max_response_bytes": 1_048_576},
        evaluator=STRICT_PATH_EVALUATOR,
    ),
    # An ORCHESTRATOR, not a seller. The capability under test is not producing
    # a quote or holding a slot — it is handing back the record of what it did,
    # and doing so without doing it again.
    #
    # `concierge.last_run` is the read. The agent's other skill runs a live
    # scenario that books a real table, so a duplicate-request profile pointed at
    # it would be asserting that a booking agent double-books; this profile
    # deliberately tests the surface where repetition is supposed to be free.
    #
    # `terminal_fulfillments: 1` and the digest match are the whole claim: the
    # same logical request delivered twice must come back byte-identical, which
    # is what distinguishes a record from a re-run.
    "a2a-orchestration-record@0.1": PathProfile(
        profile_id="a2a-orchestration-record",
        version="0.1",
        protocol="a2a",
        capability="orchestration-record",
        request={"skill": "concierge.last_run"},
        expected={"fields": {"skill": "concierge.last_run",
                             "kind": "receipt-chain"},
                  "terminal_fulfillments": 1},
        controlled_condition="duplicate_request",
        limits={"timeout_seconds": 20.0, "max_response_bytes": 4_194_304},
        evaluator=STRICT_PATH_EVALUATOR,
    ),
}

DEFAULT_PATH_PROFILE = "a2a-capability-fulfillment@0.3"


def get_path_profile(ref: str) -> PathProfile:
    if ref not in PATH_PROFILES:
        raise KeyError(f"no path profile {ref!r};"
                       f" available: {sorted(PATH_PROFILES)}")
    return PATH_PROFILES[ref]
