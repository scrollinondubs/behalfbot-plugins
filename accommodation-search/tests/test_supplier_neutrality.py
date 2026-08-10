#!/usr/bin/env python3
"""The interface is designed for two suppliers. Only one is implemented.

That is a constraint which holds right up until the afternoon somebody is in a
hurry and drops `hotelIds` into a tool schema because it is what the API call
needs anyway. Six months later Booking.com approval lands and the "swap in a
second supplier" plan turns out to mean rewriting every caller.

So the constraint is a test, not a note in a README. If a supplier's dialect
reaches the public tool surface, this suite fails.

Run:  python3 accommodation-search/tests/test_supplier_neutrality.py
"""
from __future__ import annotations

import json
import unittest
from datetime import date

from _harness import TOKEN_OK, fixture, make_supplier

import accommodation_errors as kinds  # noqa: E402
import mcp_server  # noqa: E402
from accommodation_errors import AccommodationError  # noqa: E402
from supplier import (  # noqa: E402
    IMPLEMENTED_SUPPLIERS,
    RESERVED_SUPPLIERS,
    Place,
    SearchQuery,
    Stay,
    split_id,
)

# Vocabulary that belongs to one supplier and must not appear in a tool's
# public schema. Amadeus spells things in camelCase and thinks in hotels and
# offer ids; Booking.com thinks in dest_id and hotel_id. A caller should be
# able to read these schemas without learning either.
SUPPLIER_DIALECT = (
    "hotelid",
    "hotelids",
    "citycode",
    "offerid",
    "checkindate",
    "checkoutdate",
    "roomquantity",
    "bestrateonly",
    "dest_id",
    "amadeus",
    "booking.com",
)

STAY = Stay(check_in=date(2026, 9, 14), check_out=date(2026, 9, 16), adults=2)
HOTEL_LIST = fixture("happy", "reference-data-locations-hotels-by-city.json")
PRICED = fixture("happy", "shopping-hotel-offers.json")


def schema_words(tool: dict) -> str:
    """Everything a caller reads to decide how to call the tool: the parameter
    names and their types. Descriptions are excluded on purpose - naming a
    supplier in prose is how the limitation gets explained, and that is
    required elsewhere."""
    schema = tool["inputSchema"]
    names = list(schema.get("properties", {}))
    for definition in schema.get("properties", {}).values():
        names.extend(str(value) for value in definition.get("enum", []) if value not in IMPLEMENTED_SUPPLIERS)
    return " ".join(names).lower()


class ToolSchemasCarryNoSuppliersDialect(unittest.TestCase):
    def test_the_three_tools_from_the_spec_are_the_three_that_exist(self):
        self.assertEqual(
            [tool["name"] for tool in mcp_server.TOOLS],
            ["search_accommodation", "accommodation_details", "list_accommodation_offers"],
        )

    def test_no_parameter_is_named_in_a_suppliers_dialect(self):
        for tool in mcp_server.TOOLS:
            words = schema_words(tool)
            for term in SUPPLIER_DIALECT:
                with self.subTest(tool=tool["name"], term=term):
                    self.assertNotIn(term, words)

    def test_parameters_are_the_travellers_vocabulary(self):
        search = mcp_server.TOOLS[0]["inputSchema"]["properties"]
        for expected in ("city_code", "check_in", "check_out", "adults", "rooms", "max_price"):
            self.assertIn(expected, search)

    def test_the_supplier_parameter_enumerates_only_what_is_implemented(self):
        supplier_property = mcp_server.TOOLS[0]["inputSchema"]["properties"]["supplier"]
        self.assertEqual(supplier_property["enum"], list(IMPLEMENTED_SUPPLIERS))
        self.assertEqual(supplier_property["default"], "amadeus")

    def test_the_reserved_supplier_is_named_so_it_cannot_be_taken_by_accident(self):
        self.assertIn("booking", RESERVED_SUPPLIERS)


class ResultsAreNeutralToo(unittest.TestCase):
    def test_a_search_result_uses_neutral_keys(self):
        found = make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, PRICED)).search(
            SearchQuery(place=Place(city_code="LON"), stay=STAY)
        )
        entry = found["results"][0]
        self.assertEqual(
            sorted(entry["property"]),
            [
                "amenities",
                "chain_code",
                "city_code",
                "coordinates",
                "country_code",
                "distance_km",
                "inventory_type",
                "name",
                "property_id",
                "supplier",
            ],
        )
        self.assertEqual(sorted(entry["offers"][0]["price"]),
                         ["average_per_night", "base", "currency", "taxes", "total_for_stay"])

    def test_every_result_says_which_supplier_answered(self):
        found = make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, PRICED)).search(
            SearchQuery(place=Place(city_code="LON"), stay=STAY)
        )
        self.assertEqual(found["supplier"], "amadeus")
        self.assertEqual(found["results"][0]["property"]["supplier"], "amadeus")

    def test_results_are_cheapest_first(self):
        found = make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, PRICED)).search(
            SearchQuery(place=Place(city_code="LON"), stay=STAY)
        )
        totals = [entry["offers"][0]["price"]["total_for_stay"] for entry in found["results"]]
        self.assertEqual(totals, ["318.40", "716.00"])

    def test_prices_survive_as_the_strings_the_supplier_sent(self):
        # Round-tripping money through a float is how 318.40 becomes
        # 318.39999999999998 in front of a customer.
        found = make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, PRICED)).search(
            SearchQuery(place=Place(city_code="LON"), stay=STAY)
        )
        self.assertIsInstance(found["results"][0]["offers"][0]["price"]["total_for_stay"], str)

    def test_cancellation_is_read_from_both_shapes_the_supplier_uses(self):
        # The schema says `cancellations` (array); every published example
        # sends `cancellation` (object). The fixture has one of each.
        found = make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, PRICED)).search(
            SearchQuery(place=Place(city_code="LON"), stay=STAY)
        )
        for entry in found["results"]:
            with self.subTest(property=entry["property"]["name"]):
                self.assertTrue(entry["offers"][0]["policies"]["cancellation"])

    def test_every_response_states_that_this_is_hotels_not_apartments(self):
        found = make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, PRICED)).search(
            SearchQuery(place=Place(city_code="LON"), stay=STAY)
        )
        self.assertIn("not apartments", found["inventory_note"])
        self.assertEqual(found["results"][0]["property"]["inventory_type"], "hotel")

    def test_every_response_states_that_nothing_gets_booked(self):
        found = make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, PRICED)).search(
            SearchQuery(place=Place(city_code="LON"), stay=STAY)
        )
        self.assertIn("never books", found["booking_note"])

    def test_the_coverage_note_counts_match_what_was_actually_done(self):
        # The note is the honesty claim - "we priced 4 of the 4 we found". If
        # those numbers drift from reality it is worse than not printing them.
        found = make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, PRICED)).search(
            SearchQuery(place=Place(city_code="LON"), stay=STAY, max_results=5)
        )
        self.assertEqual(found["properties_found"], len(HOTEL_LIST["data"]))
        self.assertEqual(found["properties_priced"], len(HOTEL_LIST["data"]))
        self.assertIn(f"{found['properties_found']} properties matched", found["_coverage_note"])

    def test_only_the_property_that_was_asked_for_comes_back(self):
        # The fixture answers with three hotels. Offers belonging to a
        # different property must not be attributed to the one requested.
        result = make_supplier(TOKEN_OK, (200, PRICED)).offers("ACLON371", STAY)
        self.assertEqual(result["property"]["property_id"], "amadeus:ACLON371")
        self.assertEqual([offer["offer_id"] for offer in result["offers"]], ["amadeus:ZBC0IYFMFV"])

    def test_a_result_says_where_the_data_came_from(self):
        found = make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, PRICED)).search(
            SearchQuery(place=Place(city_code="LON"), stay=STAY)
        )
        self.assertEqual(found["data_source"], "amadeus-test")


class IdentifiersAreNamespaced(unittest.TestCase):
    def test_a_search_result_id_names_its_supplier(self):
        found = make_supplier(TOKEN_OK, (200, HOTEL_LIST), (200, PRICED)).search(
            SearchQuery(place=Place(city_code="LON"), stay=STAY)
        )
        self.assertTrue(found["results"][0]["property"]["property_id"].startswith("amadeus:"))

    def test_an_id_round_trips_into_the_detail_tools(self):
        self.assertEqual(split_id("amadeus:MCLONGHM"), ("amadeus", "MCLONGHM"))

    def test_a_bare_id_is_refused_rather_than_assumed_to_be_amadeus(self):
        # Guessing here is what makes the second supplier's arrival a silent
        # behaviour change on every existing caller.
        with self.assertRaises(AccommodationError) as caught:
            split_id("MCLONGHM")
        self.assertEqual(caught.exception.kind, kinds.BAD_REQUEST)

    def test_an_id_from_an_unimplemented_supplier_says_so_plainly(self):
        with self.assertRaises(AccommodationError) as caught:
            split_id("booking:1234567")
        self.assertEqual(caught.exception.kind, kinds.SUPPLIER_NOT_IMPLEMENTED)
        self.assertIn("apartments", caught.exception.message)

    def test_asking_for_a_reserved_supplier_does_not_silently_fall_back(self):
        response = mcp_server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "search_accommodation",
                    "arguments": {
                        "supplier": "booking",
                        "city_code": "LON",
                        "check_in": "2026-09-14",
                        "check_out": "2026-09-16",
                    },
                },
            }
        )
        payload = json.loads(response["result"]["content"][-1]["text"])
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(payload["kind"], kinds.SUPPLIER_NOT_IMPLEMENTED)


class BadInputIsCaughtBeforeACallIsSpent(unittest.TestCase):
    """Every one of these would have cost a supplier call to discover, against
    a monthly allowance nobody can read."""

    def test_a_city_name_instead_of_a_city_code(self):
        with self.assertRaises(AccommodationError):
            Place(city_code="Lisbon")

    def test_neither_a_city_nor_a_point(self):
        with self.assertRaises(AccommodationError):
            Place()

    def test_both_a_city_and_a_point(self):
        with self.assertRaises(AccommodationError):
            Place(city_code="LIS", latitude=38.7, longitude=-9.1)

    def test_checkout_before_checkin(self):
        with self.assertRaises(AccommodationError):
            Stay(check_in=date(2026, 9, 16), check_out=date(2026, 9, 14))

    def test_a_price_ceiling_with_no_currency(self):
        with self.assertRaises(AccommodationError):
            SearchQuery(place=Place(city_code="LON"), stay=STAY, max_price=120)

    def test_more_results_than_one_pricing_call_can_cover(self):
        with self.assertRaises(AccommodationError):
            SearchQuery(place=Place(city_code="LON"), stay=STAY, max_results=50)


class TheMcpTransportBehaves(unittest.TestCase):
    def test_initialize_answers_with_the_clients_protocol_version(self):
        response = mcp_server.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18"}}
        )
        self.assertEqual(response["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("tools", response["result"]["capabilities"])

    def test_a_notification_gets_no_reply(self):
        self.assertIsNone(mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_tools_list_returns_all_three(self):
        response = mcp_server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(len(response["result"]["tools"]), 3)

    def test_an_unknown_method_is_a_jsonrpc_error_not_a_crash(self):
        response = mcp_server.handle({"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
        self.assertEqual(response["error"]["code"], -32601)

    def test_a_missing_credential_surfaces_as_a_tool_error(self):
        response = mcp_server.handle(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "search_accommodation",
                    "arguments": {"city_code": "LON", "check_in": "2026-09-14",
                                  "check_out": "2026-09-16"},
                },
            },
            env={},
        )
        payload = json.loads(response["result"]["content"][-1]["text"])
        self.assertEqual(payload["kind"], kinds.CREDENTIALS_MISSING)

    def test_an_unknown_tool_name_is_an_error_not_an_empty_answer(self):
        response = mcp_server.handle(
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
             "params": {"name": "book_accommodation", "arguments": {}}},
            env={},
        )
        self.assertTrue(response["result"]["isError"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
