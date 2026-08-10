#!/usr/bin/env python3
"""test_flight_search.py - offline suite for the flight-search plugin.

Stdlib only, no network, no pip install, per this repo's plugin-tests contract.
A fake `fli` is injected into sys.modules before the module under test is
imported, so filter construction is exercised for real without reaching Google.

The centre of gravity is the empty-versus-broken distinction. Everything else
here is scaffolding around those cases:

    empty result + healthy canary   -> status "empty"     (a real answer)
    empty result + dead canary      -> scraper_error      (an error, loudly)
    rows with no prices             -> unpriced           (an error)
    a currency we did not ask for   -> currency_mismatch  (an error)

Run:
    python3 flight-search/tests/test_flight_search.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"


# ---------------------------------------------------------------------------
# A fake `fli`, registered before the import below
# ---------------------------------------------------------------------------


class _Member:
    def __init__(self, name, value=None):
        self.name = name
        self.value = value if value is not None else name

    def __repr__(self):
        return f"<{self.name}>"


class _Enumish:
    """Enough of an Enum for the code under test: attribute and item lookup."""

    def __init__(self, names, values=None):
        values = values or {}
        self._members = {n: _Member(n, values.get(n)) for n in names}

    def __getattr__(self, item):
        try:
            return self.__dict__["_members"][item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __getitem__(self, item):
        return self._members[item]


class _Model:
    """Stands in for the pydantic filter models - records kwargs, validates nothing."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeSearchClientError(Exception):
    pass


def _install_fake_fli() -> types.ModuleType:
    models = types.ModuleType("fli.models")
    models.Airport = _Enumish(["LIS", "OPO", "JFK", "EWR", "LAX"])
    models.Airline = _Enumish(["TP", "S4", "AA"], {"TP": "TAP Portugal", "S4": "SATA International", "AA": "American"})
    models.SeatType = _Enumish(["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"])
    models.MaxStops = _Enumish(["ANY", "NON_STOP", "ONE_STOP_OR_FEWER", "TWO_OR_FEWER_STOPS"])
    models.SortBy = _Enumish(["CHEAPEST", "BEST", "TOP_FLIGHTS", "DURATION", "DEPARTURE_TIME", "ARRIVAL_TIME"])
    models.TripType = _Enumish(["ONE_WAY", "ROUND_TRIP", "MULTI_CITY"])
    models.Currency = _Enumish(["EUR", "USD", "GBP"])
    models.PassengerInfo = _Model
    models.PriceLimit = _Model
    models.TimeRestrictions = _Model
    models.LayoverRestrictions = _Model
    models.FlightSegment = _Model
    models.FlightSearchFilters = _Model
    models.DateSearchFilters = _Model

    search = types.ModuleType("fli.search")
    search.SearchFlights = _Model
    search.SearchDates = _Model
    search.SearchClientError = FakeSearchClientError

    package = types.ModuleType("fli")
    package.models = models
    package.search = search
    package.__path__ = []  # marks it as a package so submodule imports resolve

    sys.modules["fli"] = package
    sys.modules["fli.models"] = models
    sys.modules["fli.search"] = search
    return package


_install_fake_fli()
sys.path.insert(0, str(SCRIPTS))

import flight_search_mcp  # noqa: E402
import flight_tools  # noqa: E402
from flight_tools import FlightSearchError  # noqa: E402


# ---------------------------------------------------------------------------
# Result doubles
# ---------------------------------------------------------------------------


def leg(airline="TP", number="201", origin="LIS", destination="JFK"):
    return types.SimpleNamespace(
        airline=_Member(airline, "TAP Portugal"),
        flight_number=number,
        departure_airport=_Member(origin),
        arrival_airport=_Member(destination),
        departure_datetime=datetime(2026, 9, 9, 10, 0),
        arrival_datetime=datetime(2026, 9, 9, 18, 30),
        duration=510,
    )


def flight(price=442.0, currency="EUR", stops=0, duration=510):
    return types.SimpleNamespace(
        price=price, currency=currency, stops=stops, duration=duration, legs=[leg()]
    )


def day_price(date="2026-09-09", price=442.0, currency="EUR"):
    return types.SimpleNamespace(date=(datetime.strptime(date, "%Y-%m-%d"),), price=price, currency=currency)


CANARY_ORIGIN, CANARY_DESTINATION = "JFK", "LAX"


def searcher_for(route_results, canary_results=None, canary_raises=None):
    """A fake searcher. Tracked routes get `route_results`; the control route gets
    `canary_results` (default: healthy)."""
    canary_results = [flight(199.0)] if canary_results is None else canary_results

    def _search(query, currency, limit=5):
        if query["origin"].upper() == CANARY_ORIGIN and query["destination"].upper() == CANARY_DESTINATION:
            if canary_raises:
                raise canary_raises
            return list(canary_results)
        if isinstance(route_results, Exception):
            raise route_results
        return list(route_results)

    return _search


class Base(unittest.TestCase):
    def setUp(self):
        flight_tools.reset_canary_cache()
        self._tmp = tempfile.TemporaryDirectory()
        self.store = pathlib.Path(self._tmp.name) / "nested" / "tracked-routes.json"

    def tearDown(self):
        self._tmp.cleanup()

    def a_query(self, **overrides):
        query = {
            "origin": "LIS",
            "destination": "JFK",
            "date": (datetime.now() + timedelta(days=40)).strftime("%Y-%m-%d"),
            "cabin": "economy",
            "max_stops": "any",
        }
        query.update(overrides)
        return query


# ---------------------------------------------------------------------------
# The distinction the whole plugin exists to make
# ---------------------------------------------------------------------------


class TestEmptyVersusBroken(Base):
    def test_empty_with_healthy_canary_is_a_genuine_empty(self):
        searcher = searcher_for([])
        out = flight_tools.interpret_results([], "EUR", searcher)
        self.assertEqual(out["status"], "empty")
        self.assertEqual(out["flights"], [])
        self.assertIn("priced flights", out["canary"])

    def test_empty_with_empty_canary_is_a_scraper_error(self):
        searcher = searcher_for([], canary_results=[])
        with self.assertRaises(FlightSearchError) as ctx:
            flight_tools.interpret_results([], "EUR", searcher)
        self.assertEqual(ctx.exception.kind, "scraper_error")

    def test_empty_with_failing_canary_is_a_scraper_error(self):
        searcher = searcher_for([], canary_raises=FlightSearchError("http_error", "429 from Google"))
        with self.assertRaises(FlightSearchError) as ctx:
            flight_tools.interpret_results([], "EUR", searcher)
        self.assertEqual(ctx.exception.kind, "scraper_error")

    def test_canary_priced_at_none_counts_as_unhealthy(self):
        searcher = searcher_for([], canary_results=[flight(price=None)])
        with self.assertRaises(FlightSearchError) as ctx:
            flight_tools.interpret_results([], "EUR", searcher)
        self.assertEqual(ctx.exception.kind, "scraper_error")

    def test_rows_with_no_prices_are_an_error_not_an_answer(self):
        searcher = searcher_for([])
        with self.assertRaises(FlightSearchError) as ctx:
            flight_tools.interpret_results([flight(price=None), flight(price=None)], "EUR", searcher)
        self.assertEqual(ctx.exception.kind, "unpriced")

    def test_wrong_currency_is_an_error_not_a_price(self):
        searcher = searcher_for([])
        with self.assertRaises(FlightSearchError) as ctx:
            flight_tools.interpret_results([flight(442.0, currency="USD")], "EUR", searcher)
        self.assertEqual(ctx.exception.kind, "currency_mismatch")

    def test_canary_is_asked_once_per_process(self):
        calls = []

        def counting(query, currency, limit=5):
            calls.append(query["origin"])
            if query["origin"] == CANARY_ORIGIN:
                return [flight(199.0)]
            return []

        flight_tools.interpret_results([], "EUR", counting)
        flight_tools.interpret_results([], "EUR", counting)
        self.assertEqual(calls.count(CANARY_ORIGIN), 1)

    def test_ok_result_is_sorted_cheapest_first_and_limited(self):
        searcher = searcher_for([])
        rows = [flight(500.0), flight(300.0), flight(400.0)]
        out = flight_tools.interpret_results(rows, "EUR", searcher, limit=2)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["cheapest_price"], 300.0)
        self.assertEqual([f["price"] for f in out["flights"]], [300.0, 400.0])
        self.assertEqual(out["count"], 3)


# ---------------------------------------------------------------------------
# Filter construction against the fake fli
# ---------------------------------------------------------------------------


class TestFilters(Base):
    def test_multi_airport_origin_and_destination(self):
        fli = flight_tools._load_fli()
        filters = flight_tools.build_flight_filters(fli, self.a_query(origin="LIS,OPO", destination="JFK,EWR"), "EUR")
        segment = filters.flight_segments[0]
        self.assertEqual([a[0].name for a in segment.departure_airport], ["LIS", "OPO"])
        self.assertEqual([a[0].name for a in segment.arrival_airport], ["JFK", "EWR"])

    def test_unknown_airport_is_a_bad_request(self):
        fli = flight_tools._load_fli()
        with self.assertRaises(FlightSearchError) as ctx:
            flight_tools.build_flight_filters(fli, self.a_query(origin="ZZZ"), "EUR")
        self.assertEqual(ctx.exception.kind, "bad_request")

    def test_non_iata_origin_is_rejected_before_lookup(self):
        fli = flight_tools._load_fli()
        with self.assertRaises(FlightSearchError):
            flight_tools.build_flight_filters(fli, self.a_query(origin="Lisbon"), "EUR")

    def test_time_windows_reach_the_filters(self):
        fli = flight_tools._load_fli()
        query = self.a_query(depart_after=6, depart_before=20, arrive_before=23)
        filters = flight_tools.build_flight_filters(fli, query, "EUR")
        restrictions = filters.flight_segments[0].time_restrictions
        self.assertEqual(restrictions.earliest_departure, 6)
        self.assertEqual(restrictions.latest_departure, 20)
        self.assertEqual(restrictions.latest_arrival, 23)

    def test_out_of_range_hour_is_rejected(self):
        fli = flight_tools._load_fli()
        with self.assertRaises(FlightSearchError):
            flight_tools.build_flight_filters(fli, self.a_query(depart_after=99), "EUR")

    def test_price_ceiling_carries_the_requested_currency(self):
        fli = flight_tools._load_fli()
        filters = flight_tools.build_flight_filters(fli, self.a_query(max_price=350), "EUR")
        self.assertEqual(filters.price_limit.max_price, 350)
        self.assertEqual(filters.price_limit.currency.name, "EUR")

    def test_airline_restriction_resolves_codes(self):
        fli = flight_tools._load_fli()
        filters = flight_tools.build_flight_filters(fli, self.a_query(airlines="TP,AA"), "EUR")
        self.assertEqual([a.name for a in filters.airlines], ["TP", "AA"])

    def test_bad_date_is_rejected(self):
        fli = flight_tools._load_fli()
        with self.assertRaises(FlightSearchError):
            flight_tools.build_flight_filters(fli, self.a_query(date="09/09/2026"), "EUR")

    def test_max_layover_and_duration_reach_the_filters(self):
        fli = flight_tools._load_fli()
        query = self.a_query(max_layover_minutes=180, max_duration_minutes=900)
        filters = flight_tools.build_flight_filters(fli, query, "EUR")
        self.assertEqual(filters.layover_restrictions.max_duration, 180)
        self.assertEqual(filters.max_duration, 900)


# ---------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------


class TestStore(Base):
    def test_track_then_list_then_remove(self):
        query = self.a_query()
        created = flight_tools.track_flight(query, 300.0, currency="EUR", path=self.store)
        self.assertEqual(created["action"], "created")
        rid = created["route"]["id"]

        listed = flight_tools.list_tracked(self.store)
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["routes"][0]["target_price"], 300.0)

        removed = flight_tools.remove_tracked(rid, self.store)
        self.assertEqual(removed["remaining"], 0)

    def test_store_is_written_to_disk_and_reloads(self):
        """The container-rebuild criterion: state lives in a file, not in memory."""
        query = self.a_query()
        flight_tools.track_flight(query, 300.0, path=self.store)
        self.assertTrue(self.store.exists())
        reloaded = json.loads(self.store.read_text(encoding="utf-8"))
        self.assertEqual(reloaded["schema"], flight_tools.STORE_SCHEMA)
        self.assertEqual(len(reloaded["routes"]), 1)
        self.assertEqual(flight_tools.list_tracked(self.store)["count"], 1)

    def test_tracking_the_same_route_twice_updates_rather_than_duplicates(self):
        query = self.a_query()
        flight_tools.track_flight(query, 300.0, path=self.store)
        second = flight_tools.track_flight(query, 250.0, path=self.store)
        self.assertEqual(second["action"], "updated")
        self.assertEqual(flight_tools.list_tracked(self.store)["count"], 1)
        self.assertEqual(second["route"]["target_price"], 250.0)

    def test_route_id_separates_different_cabins(self):
        economy = flight_tools.route_id(self.a_query())
        business = flight_tools.route_id(self.a_query(cabin="business"))
        self.assertNotEqual(economy, business)

    def test_target_price_is_required(self):
        with self.assertRaises(FlightSearchError) as ctx:
            flight_tools.track_flight(self.a_query(), None, path=self.store)
        self.assertEqual(ctx.exception.kind, "bad_request")

    def test_removing_an_unknown_route_is_an_error(self):
        with self.assertRaises(FlightSearchError) as ctx:
            flight_tools.remove_tracked("nope", self.store)
        self.assertEqual(ctx.exception.kind, "not_found")

    def test_corrupt_store_refuses_rather_than_reading_as_empty(self):
        self.store.parent.mkdir(parents=True, exist_ok=True)
        self.store.write_text("{ this is not json", encoding="utf-8")
        with self.assertRaises(FlightSearchError) as ctx:
            flight_tools.load_store(self.store)
        self.assertEqual(ctx.exception.kind, "store_error")


# ---------------------------------------------------------------------------
# Alert policy
# ---------------------------------------------------------------------------


class TestAlertPolicy(Base):
    def _route(self, **overrides):
        route = {
            "id": "LIS-JFK-2026-09-09-abc123",
            "label": "test",
            "target_price": 300.0,
            "currency": "EUR",
            "history": [{"ts_utc": "2026-08-01T00:00:00+00:00", "price": 442.0, "currency": "EUR"}],
            "last_alert": None,
        }
        route.update(overrides)
        return route

    def test_above_target_is_silent(self):
        self.assertIsNone(flight_tools.evaluate_price(self._route(), 420.0, flight_tools.now_utc()))

    def test_crossing_the_target_alerts(self):
        alert = flight_tools.evaluate_price(self._route(), 280.0, flight_tools.now_utc())
        self.assertIsNotNone(alert)
        self.assertEqual(alert["kind"], "target_met")
        self.assertEqual(alert["previous_price"], 442.0)

    def test_at_the_target_alerts(self):
        self.assertIsNotNone(flight_tools.evaluate_price(self._route(), 300.0, flight_tools.now_utc()))

    def test_staying_below_target_does_not_re_alert(self):
        route = self._route(last_alert={"kind": "target_met", "price": 280.0, "ts_utc": "2026-08-01T00:00:00+00:00"})
        self.assertIsNone(flight_tools.evaluate_price(route, 280.0, flight_tools.now_utc()))
        self.assertIsNone(flight_tools.evaluate_price(route, 290.0, flight_tools.now_utc()))

    def test_dropping_further_alerts_again(self):
        route = self._route(last_alert={"kind": "target_met", "price": 280.0, "ts_utc": "2026-08-01T00:00:00+00:00"})
        self.assertIsNotNone(flight_tools.evaluate_price(route, 240.0, flight_tools.now_utc()))

    def test_no_target_means_no_price_alert(self):
        self.assertIsNone(flight_tools.evaluate_price(self._route(target_price=None), 10.0, flight_tools.now_utc()))


# ---------------------------------------------------------------------------
# check_prices
# ---------------------------------------------------------------------------


class TestCheckPrices(Base):
    def _tracked(self, target=300.0):
        return flight_tools.track_flight(self.a_query(), target, currency="EUR", path=self.store)["route"]["id"]

    def test_a_price_drop_produces_exactly_one_alert(self):
        rid = self._tracked()
        searcher = searcher_for([flight(250.0)])
        first = flight_tools.check_prices(path=self.store, searcher=searcher)
        self.assertEqual(len(first["alerts"]), 1)
        self.assertEqual(first["alerts"][0]["route_id"], rid)

        flight_tools.reset_canary_cache()
        second = flight_tools.check_prices(path=self.store, searcher=searcher)
        self.assertEqual(second["alerts"], [])

    def test_no_movement_is_silent_and_still_records_a_point(self):
        self._tracked()
        searcher = searcher_for([flight(442.0)])
        result = flight_tools.check_prices(path=self.store, searcher=searcher)
        self.assertEqual(result["alerts"], [])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(flight_tools.list_tracked(self.store)["routes"][0]["points"], 1)

    def test_every_price_point_carries_a_timestamp(self):
        self._tracked()
        flight_tools.check_prices(path=self.store, searcher=searcher_for([flight(442.0)]))
        point = flight_tools.list_tracked(self.store)["routes"][0]["history"][0]
        self.assertIn("ts_utc", point)
        datetime.fromisoformat(point["ts_utc"])
        self.assertEqual(point["currency"], "EUR")

    def test_a_broken_scraper_alerts_and_never_reads_as_no_change(self):
        """The acceptance criterion: an empty result with a dead canary is an error."""
        self._tracked()
        searcher = searcher_for([], canary_results=[])
        result = flight_tools.check_prices(path=self.store, searcher=searcher)
        self.assertEqual(result["status"], "error")
        self.assertEqual(len(result["alerts"]), 1)
        self.assertEqual(result["alerts"][0]["kind"], "error")
        self.assertEqual(result["alerts"][0]["error_kind"], "scraper_error")
        self.assertEqual(result["errors"][0]["error_kind"], "scraper_error")
        # No price point was invented for a route that could not be priced.
        self.assertEqual(flight_tools.list_tracked(self.store)["routes"][0]["points"], 0)

    def test_an_empty_route_with_a_healthy_canary_is_still_an_error_not_a_price(self):
        self._tracked()
        searcher = searcher_for([])  # canary healthy by default
        result = flight_tools.check_prices(path=self.store, searcher=searcher)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"][0]["error_kind"], "empty_route")

    def test_an_upstream_exception_surfaces_as_an_error(self):
        self._tracked()
        searcher = searcher_for(FlightSearchError("http_error", "503 from Google"))
        result = flight_tools.check_prices(path=self.store, searcher=searcher)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"][0]["error_kind"], "http_error")

    def test_a_route_that_stays_broken_does_not_alert_daily(self):
        self._tracked()
        searcher = searcher_for([], canary_results=[])
        start = flight_tools.now_utc()
        first = flight_tools.check_prices(path=self.store, searcher=searcher, now=start)
        self.assertEqual(len(first["alerts"]), 1)
        next_day = flight_tools.check_prices(path=self.store, searcher=searcher, now=start + timedelta(days=1))
        self.assertEqual(next_day["alerts"], [])
        self.assertEqual(next_day["status"], "error")  # still reported, just not re-alerted

    def test_a_long_outage_re_alerts_after_the_repeat_window(self):
        self._tracked()
        searcher = searcher_for([], canary_results=[])
        start = flight_tools.now_utc()
        flight_tools.check_prices(path=self.store, searcher=searcher, now=start)
        later = flight_tools.check_prices(path=self.store, searcher=searcher, now=start + timedelta(days=4))
        self.assertEqual(len(later["alerts"]), 1)

    def test_recovery_is_announced(self):
        self._tracked()
        broken = searcher_for([], canary_results=[])
        flight_tools.check_prices(path=self.store, searcher=broken, now=flight_tools.now_utc())
        flight_tools.reset_canary_cache()
        healed = searcher_for([flight(442.0)])
        result = flight_tools.check_prices(path=self.store, searcher=healed)
        self.assertEqual([a["kind"] for a in result["alerts"]], ["recovered"])
        self.assertEqual(result["status"], "ok")

    def test_history_is_capped(self):
        self._tracked()
        searcher = searcher_for([flight(442.0)])
        for _ in range(5):
            flight_tools.reset_canary_cache()
            flight_tools.check_prices(path=self.store, searcher=searcher)
        points = flight_tools.list_tracked(self.store)["routes"][0]["points"]
        self.assertLessEqual(points, flight_tools.max_history_points())
        self.assertEqual(points, 5)

    def test_simulated_drop_is_flagged_in_the_history(self):
        rid = self._tracked()
        result = flight_tools.check_prices(path=self.store, searcher=searcher_for([flight(442.0)]),
                                           simulate_drop={rid: 199.0})
        self.assertEqual(result["alerts"][0]["kind"], "target_met")
        self.assertTrue(result["alerts"][0]["simulated"])
        self.assertTrue(flight_tools.list_tracked(self.store)["routes"][0]["history"][-1]["simulated"])

    def test_simulated_failure_produces_the_error_path(self):
        self._tracked()
        result = flight_tools.check_prices(path=self.store, searcher=searcher_for([flight(442.0)]),
                                           simulate_failure={"all"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["alerts"][0]["error_kind"], "scraper_error")

    def test_one_broken_route_does_not_hide_a_working_one(self):
        good_id = self._tracked()
        other = self.a_query(destination="EWR")
        flight_tools.track_flight(other, 300.0, currency="EUR", path=self.store)

        def mixed(query, currency, limit=5):
            if query["origin"].upper() == CANARY_ORIGIN:
                return [flight(199.0)]
            if query["destination"].upper() == "EWR":
                raise FlightSearchError("http_error", "503 from Google")
            return [flight(442.0)]

        result = flight_tools.check_prices(path=self.store, searcher=mixed)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["checked"], 2)
        priced = [r for r in result["routes"] if r["status"] == "ok"]
        self.assertEqual([r["id"] for r in priced], [good_id])


# ---------------------------------------------------------------------------
# search_dates
# ---------------------------------------------------------------------------


class TestSearchDates(Base):
    def _query(self):
        return {
            "origin": "LIS",
            "destination": "JFK",
            "from_date": "2026-09-09",
            "to_date": "2026-09-12",
        }

    def test_cheapest_day_is_identified(self):
        days = [day_price("2026-09-09", 442.0), day_price("2026-09-10", 399.0), day_price("2026-09-11", 501.0)]
        out = flight_tools.search_dates(
            self._query(), currency="EUR",
            searcher=lambda q, c: days,
            flight_searcher=searcher_for([]),
        )
        self.assertEqual(out["cheapest"]["date"], "2026-09-10")
        self.assertEqual(out["spread"], 102.0)

    def test_empty_grid_with_a_dead_canary_is_a_scraper_error(self):
        with self.assertRaises(FlightSearchError) as ctx:
            flight_tools.search_dates(
                self._query(), currency="EUR",
                searcher=lambda q, c: [],
                flight_searcher=searcher_for([], canary_results=[]),
            )
        self.assertEqual(ctx.exception.kind, "scraper_error")

    def test_wrong_currency_in_the_grid_is_an_error(self):
        with self.assertRaises(FlightSearchError) as ctx:
            flight_tools.search_dates(
                self._query(), currency="EUR",
                searcher=lambda q, c: [day_price("2026-09-09", 442.0, "USD")],
                flight_searcher=searcher_for([]),
            )
        self.assertEqual(ctx.exception.kind, "currency_mismatch")


# ---------------------------------------------------------------------------
# The MCP surface
# ---------------------------------------------------------------------------


class TestMcpServer(Base):
    def test_initialize_echoes_the_requested_protocol(self):
        response = flight_search_mcp.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-03-26"}}
        )
        self.assertEqual(response["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(response["result"]["serverInfo"]["name"], "flight-search")

    def test_notifications_get_no_response(self):
        self.assertIsNone(flight_search_mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_all_six_tools_are_advertised_with_schemas(self):
        response = flight_search_mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = sorted(t["name"] for t in response["result"]["tools"])
        self.assertEqual(
            names,
            ["check_prices", "list_tracked", "remove_tracked", "search_dates", "search_flights", "track_flight"],
        )
        for tool in response["result"]["tools"]:
            self.assertIn("inputSchema", tool)
            self.assertIn("description", tool)

    def test_unknown_method_is_a_jsonrpc_error(self):
        response = flight_search_mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/nope"})
        self.assertEqual(response["error"]["code"], -32601)

    def test_a_tool_failure_comes_back_as_iserror(self):
        result = flight_search_mcp.call_tool("remove_tracked", {"route_id": "does-not-exist"})
        self.assertTrue(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["error_kind"], "not_found")

    def test_an_unknown_tool_is_an_error_not_a_crash(self):
        result = flight_search_mcp.call_tool("book_me_a_yacht", {})
        self.assertTrue(result["isError"])

    def test_tool_names_match_the_manifest_contract(self):
        manifest = json.loads(
            (pathlib.Path(__file__).resolve().parent.parent / "openclaw.plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            sorted(manifest["contracts"]["tools"]),
            sorted(t["name"] for t in flight_search_mcp.TOOLS),
        )


class TestErrorEnvelope(Base):
    def test_error_dict_names_the_kind(self):
        payload = FlightSearchError("scraper_error", "boom", "detail").to_dict()
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_kind"], "scraper_error")
        self.assertEqual(payload["detail"], "detail")

    def test_missing_dependency_is_named(self):
        saved = {name: sys.modules.pop(name) for name in ("fli", "fli.models", "fli.search")}
        sys.modules["fli"] = None  # an import of a None entry raises ImportError
        try:
            with self.assertRaises(FlightSearchError) as ctx:
                flight_tools._load_fli()
            self.assertEqual(ctx.exception.kind, "dependency_missing")
        finally:
            sys.modules.update(saved)

    def test_timestamps_are_utc_and_second_resolution(self):
        stamped = flight_tools.iso(datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(stamped, "2026-08-10T12:00:00+00:00")


if __name__ == "__main__":
    unittest.main(verbosity=2)
