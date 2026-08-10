#!/usr/bin/env python3
"""Failure vocabulary for accommodation search, and the rule that an empty
result is one of the failures.

The rule
========
An empty or failed search surfaces as an error. Never as "nothing available".

That rule arrived from a scraper - a rotted selector returns an empty list that
is byte-identical to a search which genuinely matched nothing. An official API
does not rot that way, so it is worth writing down why the rule still holds
here.

A supplier API returns zero results for at least five reasons that look the
same from the caller's side:

  - the property list really is sold out on those dates
  - the geocode or city code resolved somewhere other than where the traveller
    meant, so the properties priced were the wrong properties
  - the price ceiling or the board type filtered every offer out
  - the account's test environment carries only a subset of chains, so the
    inventory being searched is not the inventory that exists
  - the supplier degraded and answered with an empty body rather than an error

Only the first of those is a fact about the world. The other four are facts
about the request. A travel assistant that reports "there is nothing available
in Lisbon that week" when the truth was "the city code was wrong" has told
someone something false about their trip, and they have no way to catch it.

So every zero-result path in this plugin raises. The caller gets a named
failure and instructions, not an empty list.

Every class here is supplier-neutral. Amadeus response codes are translated
into this vocabulary in amadeus_client.py; a second supplier translates into
the same vocabulary and callers never learn which one answered.
"""
from __future__ import annotations

# Failure kinds. These strings appear in tool output and are what a caller
# branches on, so they are part of the plugin's contract - change them like an
# API, not like an internal enum.
CREDENTIALS_MISSING = "CREDENTIALS_MISSING"
AUTH_FAILED = "AUTH_FAILED"
RATE_LIMITED = "RATE_LIMITED"
QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
LOCAL_BUDGET_EXHAUSTED = "LOCAL_BUDGET_EXHAUSTED"
BAD_REQUEST = "BAD_REQUEST"
SUPPLIER_REPORTED_NO_MATCH = "SUPPLIER_REPORTED_NO_MATCH"
EMPTY_RESULT = "EMPTY_RESULT"
SUPPLIER_ERROR = "SUPPLIER_ERROR"
TRANSPORT_ERROR = "TRANSPORT_ERROR"
SUPPLIER_NOT_IMPLEMENTED = "SUPPLIER_NOT_IMPLEMENTED"

# The three kinds an operator most often confuses, and the reason they are
# separate classes rather than one "quota problem" bucket. Retrying a
# RATE_LIMITED call in a few seconds works. Retrying a QUOTA_EXHAUSTED call
# will not work until the calendar month turns over. Retrying a
# LOCAL_BUDGET_EXHAUSTED call works the moment a human raises the local budget,
# and the supplier was never even asked.
RETRYABLE_KINDS = frozenset({RATE_LIMITED, TRANSPORT_ERROR, SUPPLIER_ERROR})


class AccommodationError(Exception):
    """A named failure with enough detail for an agent to act on it.

    `kind` is the branch point. `what_to_do` is written for a reader who is
    going to relay it to a human, so it says what to tell them as well as what
    to try.
    """

    def __init__(
        self,
        kind: str,
        message: str,
        what_to_do: list[str] | None = None,
        supplier: str | None = None,
        detail: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.what_to_do = what_to_do or []
        self.supplier = supplier
        self.detail = detail or {}

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE_KINDS

    def to_payload(self) -> dict:
        payload = {
            "status": "ERROR",
            "kind": self.kind,
            "message": self.message,
            "retryable": self.retryable,
            "what_to_do": list(self.what_to_do),
        }
        if self.supplier:
            payload["supplier"] = self.supplier
        if self.detail:
            payload["detail"] = dict(self.detail)
        return payload


NEVER_SAY_NOTHING_AVAILABLE = (
    "Do not report this to the traveller as 'nothing available'. The search "
    "returned zero results and this plugin cannot tell whether that is a fact "
    "about availability or a fact about the request."
)


def empty_result(
    what_was_searched: str,
    what_to_do: list[str],
    supplier: str | None = None,
    detail: dict | None = None,
) -> AccommodationError:
    """The zero-result error. One constructor so the wording cannot drift."""
    return AccommodationError(
        kind=EMPTY_RESULT,
        message=(
            f"EMPTY RESULT - this is an error, not an answer. {what_was_searched} "
            f"returned zero results. {NEVER_SAY_NOTHING_AVAILABLE}"
        ),
        what_to_do=list(what_to_do) + [
            "Tell the traveller what actually happened: the search came back "
            "empty and it could not be confirmed whether that reflects real "
            "availability."
        ],
        supplier=supplier,
        detail=detail,
    )
