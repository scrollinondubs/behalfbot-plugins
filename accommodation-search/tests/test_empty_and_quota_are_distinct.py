#!/usr/bin/env python3
"""The two acceptance criteria this whole plugin is shaped around.

    1. An empty or failed search surfaces as an error, never as
       "nothing available".
    2. A quota-exhausted response is distinguishable from a genuinely empty
       search.

The second is the one that is easy to get wrong and expensive when it is. Both
a rate limit and an exhausted monthly quota arrive as HTTP 429 from Amadeus, and
they mean opposite things: one clears in a second, the other clears when the
calendar month does. An agent that treats them the same either retries for three
weeks or gives up on a search that would have worked on the next attempt. And
both of those are different again from "the supplier answered, and the answer
was empty", which is not a failure of the plumbing at all.

Run:  python3 accommodation-search/tests/test_empty_and_quota_are_distinct.py
"""
from __future__ import annotations

import json
import unittest
from datetime import date

from _harness import TOKEN_OK, fixture, make_supplier, temp_budget

import accommodation_errors as kinds  # noqa: E402
import mcp_server  # noqa: E402
from accommodation_errors import AccommodationError  # noqa: E402
from supplier import Place, SearchQuery, Stay  # noqa: E402

STAY = Stay(check_in=date(2026, 9, 14), check_out=date(2026, 9, 16), adults=2)
QUERY = SearchQuery(place=Place(city_code="LON"), stay=STAY, max_results=10)

HOTEL_LIST = fixture("happy", "reference-data-locations-hotels-by-city.json")
PRICED = fixture("happy", "shopping-hotel-offers.json")


def run_search(*responses, budget=None):
    return make_supplier(TOKEN_OK, *responses, budget=budget).search(QUERY)


class AnEmptySearchIsAnError(unittest.TestCase):
    def test_empty_property_list_raises_rather_than_returning_nothing(self):
        with self.assertRaises(AccommodationError) as caught:
            run_search((200, {"data": []}))
        self.assertEqual(caught.exception.kind, kinds.EMPTY_RESULT)

    def test_empty_pricing_raises_even_when_properties_were_found(self):
        with self.assertRaises(AccommodationError) as caught:
            run_search((200, HOTEL_LIST), (200, {"data": []}))
        self.assertEqual(caught.exception.kind, kinds.EMPTY_RESULT)

    def test_the_error_forbids_the_nothing_available_reading_in_words(self):
        with self.assertRaises(AccommodationError) as caught:
            run_search((200, HOTEL_LIST), (200, {"data": []}))
        self.assertIn("nothing available", caught.exception.message)

    def test_the_error_says_how_many_properties_went_unpriced(self):
        # "4 found, 4 priced, none available" and "4 found, 1 priced" are
        # different situations and the traveller-facing answer differs.
        with self.assertRaises(AccommodationError) as caught:
            run_search((200, HOTEL_LIST), (200, {"data": []}))
        self.assertEqual(caught.exception.detail["properties_found"], 4)

    def test_a_property_with_an_empty_offers_array_is_not_counted_as_a_result(self):
        # The third hotel in the fixture is available:false with offers:[].
        # Passing that through as a result is how "we found you 3 hotels" ends
        # up including one that cannot be booked.
        found = run_search((200, HOTEL_LIST), (200, PRICED))
        self.assertEqual(len(found["results"]), 2)

    def test_offers_with_no_bookable_rate_raise_rather_than_return_empty(self):
        with self.assertRaises(AccommodationError) as caught:
            make_supplier(TOKEN_OK, (200, {"data": []})).offers("MCLONGHM", STAY)
        self.assertEqual(caught.exception.kind, kinds.EMPTY_RESULT)

    def test_details_for_an_unknown_property_raise(self):
        with self.assertRaises(AccommodationError) as caught:
            make_supplier(TOKEN_OK, (200, {"data": []})).details("ZZZZZZZZ")
        self.assertEqual(caught.exception.kind, kinds.EMPTY_RESULT)


class QuotaIsNotEmptinessAndNotRateLimiting(unittest.TestCase):
    def test_quota_exhausted_has_its_own_kind(self):
        with self.assertRaises(AccommodationError) as caught:
            run_search((200, fixture("errors", "quota-exhausted-38195.json")))
        self.assertEqual(caught.exception.kind, kinds.QUOTA_EXHAUSTED)

    def test_rate_limited_has_its_own_kind_despite_the_same_http_status(self):
        with self.assertRaises(AccommodationError) as caught:
            run_search((200, fixture("errors", "rate-limited-38194.json")))
        self.assertEqual(caught.exception.kind, kinds.RATE_LIMITED)

    def test_the_three_outcomes_are_three_different_kinds(self):
        outcomes = set()
        for response in (
            {"data": []},
            fixture("errors", "quota-exhausted-38195.json"),
            fixture("errors", "rate-limited-38194.json"),
        ):
            with self.assertRaises(AccommodationError) as caught:
                run_search((200, response))
            outcomes.add(caught.exception.kind)
        self.assertEqual(
            outcomes, {kinds.EMPTY_RESULT, kinds.QUOTA_EXHAUSTED, kinds.RATE_LIMITED}
        )

    def test_rate_limiting_is_retryable_and_quota_exhaustion_is_not(self):
        with self.assertRaises(AccommodationError) as rate_limited:
            run_search((200, fixture("errors", "rate-limited-38194.json")))
        with self.assertRaises(AccommodationError) as quota:
            run_search((200, fixture("errors", "quota-exhausted-38195.json")))
        self.assertTrue(rate_limited.exception.retryable)
        self.assertFalse(quota.exception.retryable)

    def test_the_quota_error_says_retrying_will_not_help(self):
        with self.assertRaises(AccommodationError) as caught:
            run_search((200, fixture("errors", "quota-exhausted-38195.json")))
        self.assertIn("next calendar month", " ".join(caught.exception.what_to_do))

    def test_a_quota_failure_mid_search_does_not_return_the_unpriced_list(self):
        # The property list succeeded and the pricing call hit the quota. The
        # tempting bug is answering with the four properties and no prices, as
        # if that were a result.
        with self.assertRaises(AccommodationError) as caught:
            run_search((200, HOTEL_LIST), (200, fixture("errors", "quota-exhausted-38195.json")))
        self.assertEqual(caught.exception.kind, kinds.QUOTA_EXHAUSTED)

    def test_supplier_reported_no_match_is_its_own_kind(self):
        # 424 NO HOTELS FOUND is the supplier saying so out loud, which is not
        # the same signal as a silent empty list.
        with self.assertRaises(AccommodationError) as caught:
            run_search((200, fixture("errors", "no-hotels-found-424.json")))
        self.assertEqual(caught.exception.kind, kinds.SUPPLIER_REPORTED_NO_MATCH)


class TheLocalBudgetIsNotTheSuppliersQuota(unittest.TestCase):
    def test_a_search_past_the_local_ceiling_never_reaches_the_supplier(self):
        budget = temp_budget(monthly_budget=2)
        budget.record("hotel-list")
        budget.record("hotel-offers")
        with self.assertRaises(AccommodationError) as caught:
            # No transport responses queued: reaching the network at all would
            # raise "unexpected extra request" instead.
            make_supplier(budget=budget).search(QUERY)
        self.assertEqual(caught.exception.kind, kinds.LOCAL_BUDGET_EXHAUSTED)

    def test_the_local_ceiling_says_the_supplier_refused_nothing(self):
        budget = temp_budget(monthly_budget=1)
        budget.record("hotel-list")
        with self.assertRaises(AccommodationError) as caught:
            make_supplier(budget=budget).search(QUERY)
        self.assertFalse(caught.exception.detail["is_supplier_quota"])
        self.assertIn("ledger_path", caught.exception.detail)

    def test_calls_are_counted_and_reported_with_every_result(self):
        budget = temp_budget()
        found = run_search((200, HOTEL_LIST), (200, PRICED), budget=budget)
        # One token call plus the two the search costs.
        self.assertEqual(found["usage"]["supplier_calls_counted"], 3)
        self.assertEqual(found["usage"]["counted_by_endpoint"]["hotel-offers"], 1)

    def test_the_usage_block_warns_before_the_ceiling_rather_than_at_it(self):
        budget = temp_budget(monthly_budget=10)
        for _ in range(8):
            budget.record("hotel-offers")
        self.assertIn("warning", budget.usage())


class TheToolLayerSurfacesAllOfThisAsAnError(unittest.TestCase):
    """The guarantee has to survive the trip out through MCP. A well-named
    exception that gets serialised into a cheerful empty result has guaranteed
    nothing."""

    def _call(self, monkeypatched_supplier):
        original = mcp_server.build_supplier
        mcp_server.build_supplier = lambda *args, **kwargs: monkeypatched_supplier
        try:
            return mcp_server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {
                        "name": "search_accommodation",
                        "arguments": {
                            "city_code": "LON",
                            "check_in": "2026-09-14",
                            "check_out": "2026-09-16",
                            "adults": 2,
                        },
                    },
                }
            )
        finally:
            mcp_server.build_supplier = original

    def test_an_empty_search_comes_back_with_is_error_true(self):
        response = self._call(make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, {"data": []})))
        self.assertTrue(response["result"]["isError"])

    def test_the_first_content_block_names_the_failure_without_parsing_json(self):
        response = self._call(make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, {"data": []})))
        self.assertTrue(response["result"]["content"][0]["text"].startswith("EMPTY_RESULT"))

    def test_the_payload_carries_the_kind_a_caller_branches_on(self):
        response = self._call(
            make_supplier(TOKEN_OK, (200, fixture("errors", "quota-exhausted-38195.json")))
        )
        payload = json.loads(response["result"]["content"][-1]["text"])
        self.assertEqual(payload["kind"], kinds.QUOTA_EXHAUSTED)
        self.assertFalse(payload["retryable"])

    def test_a_successful_search_is_not_flagged_as_an_error(self):
        response = self._call(make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, PRICED)))
        self.assertFalse(response["result"]["isError"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
