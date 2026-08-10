#!/usr/bin/env python3
"""Translating Amadeus failures, and never leaking a credential while doing it.

Two things are being pinned down here.

The first is that Amadeus does not have one error format, it has two. The token
endpoint answers with a flat `{"error": ..., "code": ...}` object; every other
endpoint answers with `{"errors": [...]}`. And the published example for code
38191 ships `code` and `status` as strings while every other example ships them
as integers, so a parser that assumes a number gets `None` for the one field it
needed on the one response that mattered.

The second is that nothing on any failure path can carry a credential outward.
Tool output is read by a model and copied into logs. SECURITY.md treats a key
reaching either as a vulnerability, and a failure path is exactly where a
careless implementation echoes the request back.

Run:  python3 accommodation-search/tests/test_amadeus_error_translation.py
"""
from __future__ import annotations

import json
import unittest
from datetime import date

from _harness import TOKEN_OK, FakeTransport, fixture, make_client, make_supplier, temp_budget

import accommodation_errors as kinds  # noqa: E402
import mcp_server  # noqa: E402
from accommodation_errors import AccommodationError  # noqa: E402
from amadeus_client import REDACTOR, AmadeusClient, map_error  # noqa: E402
from supplier import Place, SearchQuery, Stay  # noqa: E402

STAY = Stay(check_in=date(2026, 9, 14), check_out=date(2026, 9, 16), adults=2)


class BothErrorEnvelopes(unittest.TestCase):
    def test_the_errors_array_envelope_is_read(self):
        error = map_error(429, fixture("errors", "quota-exhausted-38195.json"), "hotel-offers")
        self.assertEqual(error.kind, kinds.QUOTA_EXHAUSTED)

    def test_the_flat_token_envelope_is_read(self):
        error = map_error(401, fixture("errors", "invalid-client-38187-flat-envelope.json"), "token")
        self.assertEqual(error.kind, kinds.AUTH_FAILED)
        self.assertEqual(error.detail["supplier_code"], 38187)

    def test_string_typed_codes_are_coerced_rather_than_dropped(self):
        # The documented 38191 example ships code and status as strings.
        error = map_error(0, fixture("errors", "invalid-header-38191-string-typed.json"), "hotel-list")
        self.assertEqual(error.kind, kinds.AUTH_FAILED)
        self.assertEqual(error.detail["supplier_code"], 38191)
        self.assertEqual(error.detail["http_status"], 401)

    def test_an_unrecognised_code_falls_back_on_the_http_status(self):
        error = map_error(503, {"errors": [{"code": 999999, "title": "SOMETHING NEW"}]}, "hotel-list")
        self.assertEqual(error.kind, kinds.SUPPLIER_ERROR)

    def test_an_unparseable_body_still_produces_a_named_failure(self):
        error = map_error(502, None, "hotel-offers")
        self.assertEqual(error.kind, kinds.SUPPLIER_ERROR)
        self.assertIn("hotel-offers", error.message)

    def test_a_200_carrying_an_errors_array_is_still_a_failure(self):
        # The fixture transport answers 200 for everything; a supplier that
        # returns an error envelope under a 200 must not be read as success.
        with self.assertRaises(AccommodationError) as caught:
            make_client(TOKEN_OK, (200, fixture("errors", "no-rooms-available-3664.json"))).get(
                "/v3/shopping/hotel-offers", {}, "hotel-offers"
            )
        self.assertEqual(caught.exception.kind, kinds.SUPPLIER_REPORTED_NO_MATCH)


class CodesMapToTheRightKind(unittest.TestCase):
    CASES = {
        "quota-exhausted-38195.json": kinds.QUOTA_EXHAUSTED,
        "rate-limited-38194.json": kinds.RATE_LIMITED,
        "token-expired-38192.json": kinds.AUTH_FAILED,
        "invalid-header-38191-string-typed.json": kinds.AUTH_FAILED,
        "invalid-client-38187-flat-envelope.json": kinds.AUTH_FAILED,
        "no-hotels-found-424.json": kinds.SUPPLIER_REPORTED_NO_MATCH,
        "no-rooms-available-3664.json": kinds.SUPPLIER_REPORTED_NO_MATCH,
        "not-found-1797.json": kinds.SUPPLIER_REPORTED_NO_MATCH,
        "invalid-format-477.json": kinds.BAD_REQUEST,
    }

    def test_every_documented_code_lands_where_it_should(self):
        for name, expected in self.CASES.items():
            with self.subTest(fixture=name):
                self.assertEqual(map_error(0, fixture("errors", name), "endpoint").kind, expected)

    def test_a_rejected_parameter_is_named_in_the_detail(self):
        error = map_error(400, fixture("errors", "invalid-format-477.json"), "hotel-list")
        self.assertEqual(error.detail["supplier_source"]["parameter"], "cityCode")

    def test_every_kind_carries_actionable_next_steps(self):
        for name in self.CASES:
            with self.subTest(fixture=name):
                self.assertTrue(map_error(0, fixture("errors", name), "endpoint").what_to_do)


class NoCredentialEverLeavesThisPlugin(unittest.TestCase):
    # Not a credential: a distinctive string stood in for one, so a test can
    # assert it never reaches an output.
    PLACEHOLDER = "stand-in-for-a-credential-do-not-print"

    def test_a_supplier_error_quoting_the_secret_back_is_scrubbed(self):
        REDACTOR.register(self.PLACEHOLDER)
        error = map_error(
            400,
            {"errors": [{"code": 477, "title": "INVALID FORMAT",
                         "detail": f"bad value {self.PLACEHOLDER} in request"}]},
            "hotel-list",
        )
        self.assertNotIn(self.PLACEHOLDER, json.dumps(error.to_payload()))
        self.assertIn("[redacted]", json.dumps(error.to_payload()))

    def test_the_mcp_error_result_is_scrubbed_on_the_way_out(self):
        REDACTOR.register(self.PLACEHOLDER)
        result = mcp_server.error_result(
            AccommodationError(
                kind=kinds.AUTH_FAILED,
                message=f"rejected credential {self.PLACEHOLDER}",
                what_to_do=[f"the secret was {self.PLACEHOLDER}"],
            )
        )
        self.assertNotIn(self.PLACEHOLDER, json.dumps(result))

    def test_a_successful_result_is_scrubbed_on_the_way_out_too(self):
        REDACTOR.register(self.PLACEHOLDER)
        result = mcp_server.tool_result({"name": f"hotel {self.PLACEHOLDER}"})
        self.assertNotIn(self.PLACEHOLDER, json.dumps(result))

    def test_the_bearer_token_never_appears_in_a_result(self):
        found = make_supplier(
            TOKEN_OK,
            (200, fixture("happy", "reference-data-locations-hotels-by-city.json")),
            (200, fixture("happy", "shopping-hotel-offers.json")),
        ).search(SearchQuery(place=Place(city_code="LON"), stay=STAY))
        self.assertNotIn("test-token-value", json.dumps(mcp_server.tool_result(found)))

    def test_credentials_are_never_read_from_a_file(self):
        # The only source is the environment. An env with nothing in it must
        # fail, not fall back to a dotfile someone left lying around.
        with self.assertRaises(AccommodationError) as caught:
            AmadeusClient.from_env(env={})
        self.assertEqual(caught.exception.kind, kinds.CREDENTIALS_MISSING)
        self.assertIn("environment only", caught.exception.message)


class TokenHandling(unittest.TestCase):
    def test_the_token_is_fetched_once_and_reused(self):
        transport = FakeTransport(
            TOKEN_OK,
            (200, {"data": [{"hotelId": "MCLONGHM", "name": "A"}]}),
            (200, {"data": [{"hotelId": "MCLONGHM", "name": "A"}]}),
        )
        api = AmadeusClient(
            "id", "secret-value-here", transport=transport, budget=temp_budget(),
            sleeper=lambda _s: None,
        )
        api.get("/v1/reference-data/locations/hotels/by-hotels", {}, "hotel-list")
        api.get("/v1/reference-data/locations/hotels/by-hotels", {}, "hotel-list")
        token_calls = [r for r in transport.requests if r["url"].endswith("/token")]
        self.assertEqual(len(token_calls), 1)

    def test_the_token_is_refreshed_before_it_expires_not_after(self):
        clock = {"now": 1000.0}
        transport = FakeTransport(
            TOKEN_OK,
            (200, {"data": []}),
            TOKEN_OK,
            (200, {"data": []}),
        )
        api = AmadeusClient(
            "id", "secret-value-here", transport=transport, budget=temp_budget(),
            clock=lambda: clock["now"], sleeper=lambda _s: None,
        )
        api.get("/x", {}, "hotel-list")
        # One second before the stated expiry, inside the ten-second buffer.
        clock["now"] = 1000.0 + 1799 - 1
        api.get("/x", {}, "hotel-list")
        token_calls = [r for r in transport.requests if r["url"].endswith("/token")]
        self.assertEqual(len(token_calls), 2)

    def test_the_bearer_header_is_actually_sent(self):
        transport = FakeTransport(TOKEN_OK, (200, {"data": []}))
        api = AmadeusClient(
            "id", "secret-value-here", transport=transport, budget=temp_budget(),
            sleeper=lambda _s: None,
        )
        api.get("/x", {}, "hotel-list")
        self.assertEqual(transport.requests[-1]["headers"]["Authorization"], "Bearer test-token-value")

    def test_the_token_request_is_form_encoded_client_credentials(self):
        transport = FakeTransport(TOKEN_OK, (200, {"data": []}))
        api = AmadeusClient(
            "id", "secret-value-here", transport=transport, budget=temp_budget(),
            sleeper=lambda _s: None,
        )
        api.get("/x", {}, "hotel-list")
        token_request = transport.requests[0]
        self.assertEqual(token_request["method"], "POST")
        self.assertEqual(
            token_request["headers"]["Content-Type"], "application/x-www-form-urlencoded"
        )
        self.assertIn(b"grant_type=client_credentials", token_request["body"])

    def test_production_and_test_hit_different_hosts(self):
        self.assertIn("test.api.amadeus.com", make_client(TOKEN_OK).host)
        self.assertEqual(make_client(TOKEN_OK, environment="production").host, "https://api.amadeus.com")

    def test_a_failed_token_call_reports_auth_not_emptiness(self):
        with self.assertRaises(AccommodationError) as caught:
            make_client((401, fixture("errors", "invalid-client-38187-flat-envelope.json"))).get(
                "/x", {}, "hotel-list"
            )
        self.assertEqual(caught.exception.kind, kinds.AUTH_FAILED)


class DegradedRatingsDoNotFailTheTool(unittest.TestCase):
    """A property's reputation is a nice-to-have. Losing it must not lose the
    address, the price and the policies alongside it - but it must be visible
    that it was lost rather than that the hotel has no reviews."""

    def test_a_ratings_failure_degrades_with_a_reason(self):
        details = make_supplier(
            TOKEN_OK,
            (200, fixture("happy", "reference-data-locations-hotels-by-hotels.json")),
            (200, fixture("errors", "rate-limited-38194.json")),
        ).details("MCLONGHM")
        self.assertEqual(details["rating"]["unavailable"], kinds.RATE_LIMITED)
        self.assertEqual(details["property"]["name"], "JW MARRIOTT GROSVENOR HOUSE LONDON")

    def test_a_property_with_no_reviews_is_distinguishable_from_a_failure(self):
        details = make_supplier(
            TOKEN_OK,
            (200, fixture("happy", "reference-data-locations-hotels-by-hotels.json")),
            (200, fixture("sentiments-warning-913.json")),
        ).details("MCLONGHM")
        self.assertEqual(details["rating"]["unavailable"], "NO_REVIEW_DATA")
        self.assertIn("PROPERTIES NOT FOUND", details["rating"]["detail"])

    def test_ratings_come_through_when_they_are_there(self):
        details = make_supplier(
            TOKEN_OK,
            (200, fixture("happy", "reference-data-locations-hotels-by-hotels.json")),
            (200, fixture("happy", "e-reputation-hotel-sentiments.json")),
        ).details("MCLONGHM")
        self.assertEqual(details["rating"]["overall_rating"], 88)


if __name__ == "__main__":
    unittest.main(verbosity=2)
