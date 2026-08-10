#!/usr/bin/env python3
"""flight_tools.py - flight search and route price tracking over the `flights` package.

Six operations, exposed both as a CLI (this file) and as MCP tools
(`flight_search_mcp.py`, which imports this module):

    search_flights   prices on a route for a date
    search_dates     cheapest day across a date range
    track_flight     register a route with a target price
    check_prices     poll tracked routes, emit alerts
    list_tracked     tracked routes with price history
    remove_tracked   stop tracking

## The one design constraint that shapes everything here

`flights` (the `fli` library) scrapes Google Flights. It will break when Google
changes their response shape, and when it breaks the natural failure is an empty
list. An empty list is indistinguishable from "this route genuinely has no
flights" and, worse, from "the price did not move" once a tracker is polling on
a schedule. A monitor that goes quiet when its data source dies is worse than no
monitor: it reports good news forever.

So no code path here returns a bare empty result as success. Every outcome is
one of:

  status=ok     with at least one priced itinerary, in the requested currency
  status=empty  an empty result that a live canary query says is genuine
  status=error  everything else, with an `error_kind` naming what broke

The canary is the load-bearing part. When a search comes back empty we run a
second search on a dense, known-good control route (JFK-LAX, roughly a month
out). If the control is also empty, the scraper is broken and the original
empty result means nothing - that is `error_kind=scraper_error`. If the control
returns priced flights, the scraper works and the empty result is real.

Three more outcomes are errors rather than emptiness, for the same reason:

  unpriced          rows came back but none carried a price
  currency_mismatch Google answered in a currency we did not ask for, so the
                    number is not comparable with the price history
  dependency_missing the `flights` package is not installed

## Testability

`fli` is imported lazily, inside `_load_fli()`, never at module import time. The
test suite runs stdlib-only with no network and no pip install (see
.github/workflows/plugin-tests.yml), and injects a fake `fli` into `sys.modules`
before importing this module. Keeping the import lazy is what makes that work,
so leave it where it is.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent

STORE_SCHEMA = 1

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CABINS = {
    "economy": "ECONOMY",
    "premium_economy": "PREMIUM_ECONOMY",
    "business": "BUSINESS",
    "first": "FIRST",
}

MAX_STOPS = {
    "any": "ANY",
    "nonstop": "NON_STOP",
    "one": "ONE_STOP_OR_FEWER",
    "two": "TWO_OR_FEWER_STOPS",
}

SORTS = {
    "cheapest": "CHEAPEST",
    "best": "BEST",
    "top": "TOP_FLIGHTS",
    "duration": "DURATION",
    "departure": "DEPARTURE_TIME",
    "arrival": "ARRIVAL_TIME",
}


class FlightSearchError(Exception):
    """A named failure. `kind` is what callers branch on, never the message."""

    def __init__(self, kind: str, message: str, detail: Any = None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict:
        out = {"status": "error", "error_kind": self.kind, "error": self.message}
        if self.detail is not None:
            out["detail"] = self.detail
        return out


# ---------------------------------------------------------------------------
# Configuration - environment only, defaults documented in the manifest
# ---------------------------------------------------------------------------


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value else default


def chassis_home() -> pathlib.Path:
    return pathlib.Path(_env("CHASSIS_HOME", str(pathlib.Path.home())))


def store_path() -> pathlib.Path:
    configured = os.environ.get("FLIGHT_SEARCH_STORE")
    if configured:
        return pathlib.Path(configured)
    return chassis_home() / "data" / "flight-search" / "tracked-routes.json"


def default_currency() -> str:
    return _env("FLIGHT_SEARCH_CURRENCY", "EUR").upper()


def max_history_points() -> int:
    try:
        return max(2, int(_env("FLIGHT_SEARCH_MAX_HISTORY", "60")))
    except ValueError:
        return 60


def error_repeat_days() -> int:
    """How long a route stays quiet while it is still broken, before re-alerting.

    Zero would re-alert daily; a large number risks a break going unnoticed after
    the first shout. Three days is loud enough to be seen and quiet enough to
    ignore for a weekend.
    """
    try:
        return max(0, int(_env("FLIGHT_SEARCH_ERROR_REPEAT_DAYS", "3")))
    except ValueError:
        return 3


def canary_route() -> tuple[str, str]:
    spec = _env("FLIGHT_SEARCH_CANARY_ROUTE", "JFK-LAX")
    parts = spec.upper().split("-")
    if len(parts) != 2 or not all(parts):
        return ("JFK", "LAX")
    return (parts[0], parts[1])


def canary_lead_days() -> int:
    try:
        return max(1, int(_env("FLIGHT_SEARCH_CANARY_LEAD_DAYS", "30")))
    except ValueError:
        return 30


def default_top_n() -> int:
    """Expansion breadth for multi-leg searches. See live_flight_searcher."""
    try:
        return max(1, min(5, int(_env("FLIGHT_SEARCH_TOP_N", "2"))))
    except ValueError:
        return 2


def max_plan_searches() -> int:
    """Ceiling on how many full itinerary searches one plan_trip call may run."""
    try:
        return max(1, int(_env("FLIGHT_SEARCH_MAX_PLAN_SEARCHES", "4")))
    except ValueError:
        return 4


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds")


def _check_date(value: str, label: str) -> str:
    if not DATE_RE.match(value or ""):
        raise FlightSearchError("bad_request", f"{label} must be YYYY-MM-DD, got '{value}'")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise FlightSearchError("bad_request", f"{label} is not a real date: {exc}") from exc
    return value


def _codes(spec: str, label: str) -> list[str]:
    codes = [c.strip().upper() for c in (spec or "").split(",") if c.strip()]
    if not codes:
        raise FlightSearchError("bad_request", f"{label} is required (IATA code, or a comma-separated list)")
    for code in codes:
        if not re.match(r"^[A-Z]{3}$", code):
            raise FlightSearchError("bad_request", f"'{code}' is not a 3-letter IATA airport code")
    return codes


# ---------------------------------------------------------------------------
# The `fli` boundary
# ---------------------------------------------------------------------------


class _Fli:
    """Everything this module touches in `fli`, resolved once, in one place.

    One import site means one thing to change if the upstream surface moves, and
    one thing for the test fake to stand in for.
    """

    def __init__(self, mod_models, mod_search):
        self.Airport = mod_models.Airport
        self.Airline = mod_models.Airline
        self.PassengerInfo = mod_models.PassengerInfo
        self.SeatType = mod_models.SeatType
        self.MaxStops = mod_models.MaxStops
        self.SortBy = mod_models.SortBy
        self.TripType = mod_models.TripType
        self.Currency = mod_models.Currency
        self.PriceLimit = mod_models.PriceLimit
        self.TimeRestrictions = mod_models.TimeRestrictions
        self.LayoverRestrictions = mod_models.LayoverRestrictions
        self.FlightSegment = mod_models.FlightSegment
        self.FlightSearchFilters = mod_models.FlightSearchFilters
        self.DateSearchFilters = mod_models.DateSearchFilters
        self.SearchFlights = mod_search.SearchFlights
        self.SearchDates = mod_search.SearchDates
        self.SearchClientError = mod_search.SearchClientError


def _load_fli() -> _Fli:
    try:
        from fli import models as mod_models
        from fli import search as mod_search
    except ImportError as exc:
        raise FlightSearchError(
            "dependency_missing",
            "the `flights` package is not installed - run this plugin's setup.sh",
            str(exc),
        ) from exc
    try:
        return _Fli(mod_models, mod_search)
    except AttributeError as exc:
        raise FlightSearchError(
            "dependency_missing",
            "the installed `flights` package does not expose the API this plugin was pinned against",
            str(exc),
        ) from exc


def _enum(container, table: dict, key: str, label: str):
    try:
        return getattr(container, table[key])
    except KeyError as exc:
        raise FlightSearchError(
            "bad_request", f"unknown {label} '{key}' - one of: {', '.join(sorted(table))}"
        ) from exc


def normalize_legs(query: dict) -> list[dict]:
    """Every query is a list of legs internally, whatever shorthand it arrived in.

    One leg is one-way. Two legs that mirror each other are a round trip. Anything
    else is multi-city. Google is asked for exactly one itinerary either way - the
    legs are never searched separately and stitched together, because a stitched
    price is not a fare anyone can book.
    """
    legs = query.get("legs")
    if legs:
        out = []
        for i, leg in enumerate(legs, start=1):
            if not isinstance(leg, dict):
                raise FlightSearchError("bad_request", f"leg {i} is not an object")
            for key in ("origin", "destination", "date"):
                if not leg.get(key):
                    raise FlightSearchError("bad_request", f"leg {i} is missing '{key}'")
            out.append(
                {
                    "origin": ",".join(_codes(leg["origin"], f"leg {i} origin")),
                    "destination": ",".join(_codes(leg["destination"], f"leg {i} destination")),
                    "date": _check_date(leg["date"], f"leg {i} date"),
                }
            )
        dates = [leg["date"] for leg in out]
        if dates != sorted(dates):
            raise FlightSearchError(
                "bad_request", f"leg dates must run forwards in time, got {', '.join(dates)}"
            )
        return out

    if not query.get("origin") or not query.get("destination") or not query.get("date"):
        raise FlightSearchError(
            "bad_request", "give either origin, destination and date, or a list of legs"
        )
    first = {
        "origin": ",".join(_codes(query["origin"], "origin")),
        "destination": ",".join(_codes(query["destination"], "destination")),
        "date": _check_date(query["date"], "date"),
    }
    return_date = query.get("return_date")
    if not return_date:
        return [first]
    return_date = _check_date(return_date, "return_date")
    if return_date < first["date"]:
        raise FlightSearchError(
            "bad_request",
            f"return_date {return_date} is before the outbound date {first['date']}",
        )
    return [first, {"origin": first["destination"], "destination": first["origin"], "date": return_date}]


def trip_shape(legs: list[dict]) -> str:
    """`one_way`, `round_trip` or `multi_city`, decided by the legs themselves."""
    if len(legs) == 1:
        return "one_way"
    if (
        len(legs) == 2
        and legs[0]["origin"] == legs[1]["destination"]
        and legs[0]["destination"] == legs[1]["origin"]
    ):
        return "round_trip"
    return "multi_city"


def _airports(fli: _Fli, spec: str, label: str) -> list:
    out = []
    for code in _codes(spec, label):
        try:
            out.append([fli.Airport[code], 0])
        except KeyError as exc:
            raise FlightSearchError("bad_request", f"unknown {label} airport code '{code}'") from exc
    return out


def _airlines(fli: _Fli, spec: str | None) -> list | None:
    if not spec:
        return None
    out = []
    for code in [c.strip().upper() for c in spec.split(",") if c.strip()]:
        try:
            out.append(fli.Airline[code])
        except KeyError as exc:
            raise FlightSearchError("bad_request", f"unknown airline code '{code}'") from exc
    return out


def _time_restrictions(fli: _Fli, query: dict):
    fields = {
        "earliest_departure": query.get("depart_after"),
        "latest_departure": query.get("depart_before"),
        "earliest_arrival": query.get("arrive_after"),
        "latest_arrival": query.get("arrive_before"),
    }
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        return None
    for key, value in fields.items():
        if not 0 <= int(value) <= 24:
            raise FlightSearchError("bad_request", f"{key} must be an hour 0-24, got {value}")
    return fli.TimeRestrictions(**{k: int(v) for k, v in fields.items()})


def _price_limit(fli: _Fli, query: dict, currency: str):
    max_price = query.get("max_price")
    if max_price is None:
        return None
    try:
        cur = fli.Currency[currency]
    except KeyError as exc:
        raise FlightSearchError(
            "bad_request",
            f"max_price needs a currency Google accepts; '{currency}' is not one of them",
        ) from exc
    return fli.PriceLimit(max_price=int(max_price), currency=cur)


def _layovers(fli: _Fli, query: dict):
    max_layover = query.get("max_layover_minutes")
    if max_layover is None:
        return None
    return fli.LayoverRestrictions(max_duration=int(max_layover))


TRIP_TYPES = {"one_way": "ONE_WAY", "round_trip": "ROUND_TRIP", "multi_city": "MULTI_CITY"}


def build_flight_filters(fli: _Fli, query: dict, currency: str):
    """Turn a plain-dict query into `fli`'s FlightSearchFilters.

    One segment per leg, and the trip type set from the leg shape. Google prices
    the whole itinerary in one shopping session: for a round trip or a multi-city
    trip, `fli` sends the chosen outbound back as `selected_flight` and asks
    Google for the next leg in the context of that choice. That is what makes the
    result a real fare rather than a sum of separate searches.
    """
    legs = normalize_legs(query)
    shape = trip_shape(legs)
    restrictions = _time_restrictions(fli, query)
    segments = [
        fli.FlightSegment(
            departure_airport=_airports(fli, leg["origin"], "origin"),
            arrival_airport=_airports(fli, leg["destination"], "destination"),
            travel_date=leg["date"],
            # Hour windows apply to the first leg only. Google takes them per
            # segment, but "leave after 6am" almost never means the same thing on
            # a return four weeks later, and silently applying it to every leg
            # would quietly drop itineraries nobody asked to exclude.
            time_restrictions=restrictions if index == 0 else None,
        )
        for index, leg in enumerate(legs)
    ]
    return fli.FlightSearchFilters(
        trip_type=_enum(fli.TripType, TRIP_TYPES, shape, "trip type"),
        passenger_info=fli.PassengerInfo(
            adults=int(query.get("adults", 1)),
            children=int(query.get("children", 0)),
            infants_in_seat=int(query.get("infants_in_seat", 0)),
            infants_on_lap=int(query.get("infants_on_lap", 0)),
        ),
        flight_segments=segments,
        seat_type=_enum(fli.SeatType, CABINS, query.get("cabin", "economy"), "cabin"),
        stops=_enum(fli.MaxStops, MAX_STOPS, query.get("max_stops", "any"), "max_stops"),
        sort_by=_enum(fli.SortBy, SORTS, query.get("sort", "cheapest"), "sort"),
        price_limit=_price_limit(fli, query, currency),
        airlines=_airlines(fli, query.get("airlines")),
        max_duration=int(query["max_duration_minutes"]) if query.get("max_duration_minutes") else None,
        layover_restrictions=_layovers(fli, query),
    )


def build_date_filters(fli: _Fli, query: dict, currency: str):
    segment = fli.FlightSegment(
        departure_airport=_airports(fli, query["origin"], "origin"),
        arrival_airport=_airports(fli, query["destination"], "destination"),
        travel_date=_check_date(query["from_date"], "from_date"),
        time_restrictions=_time_restrictions(fli, query),
    )
    return fli.DateSearchFilters(
        trip_type=fli.TripType.ONE_WAY,
        passenger_info=fli.PassengerInfo(
            adults=int(query.get("adults", 1)),
            children=int(query.get("children", 0)),
        ),
        flight_segments=[segment],
        seat_type=_enum(fli.SeatType, CABINS, query.get("cabin", "economy"), "cabin"),
        stops=_enum(fli.MaxStops, MAX_STOPS, query.get("max_stops", "any"), "max_stops"),
        price_limit=_price_limit(fli, query, currency),
        airlines=_airlines(fli, query.get("airlines")),
        max_duration=int(query["max_duration_minutes"]) if query.get("max_duration_minutes") else None,
        layover_restrictions=_layovers(fli, query),
        from_date=_check_date(query["from_date"], "from_date"),
        to_date=_check_date(query["to_date"], "to_date"),
    )


def _call_upstream(fn: Callable, *args, **kwargs):
    """Run an `fli` call and translate its failures into named ones of ours."""
    fli = _load_fli()
    try:
        return fn(*args, **kwargs)
    except FlightSearchError:
        raise
    except fli.SearchClientError as exc:
        kind = "network_error"
        name = type(exc).__name__
        if "HTTP" in name:
            kind = "http_error"
        elif "Timeout" in name:
            kind = "timeout"
        raise FlightSearchError(kind, f"Google Flights request failed: {exc}", name) from exc
    except Exception as exc:  # noqa: BLE001 - a scraper's parse failures have no stable type
        raise FlightSearchError(
            "parse_error",
            "the upstream response could not be parsed - the scraper is likely broken: "
            f"{type(exc).__name__}: {exc}",
            type(exc).__name__,
        ) from exc


# ---------------------------------------------------------------------------
# Normalization and the empty/broken distinction
# ---------------------------------------------------------------------------


def _normalize_segment(result: Any) -> dict:
    """One `fli` FlightResult to a plain dict. Codes come off `.name`, names off `.value`."""
    legs = []
    for leg in getattr(result, "legs", []) or []:
        legs.append(
            {
                "airline_code": getattr(leg.airline, "name", None),
                "airline": getattr(leg.airline, "value", None),
                "flight_number": leg.flight_number,
                "from": getattr(leg.departure_airport, "name", None),
                "to": getattr(leg.arrival_airport, "name", None),
                "departs": leg.departure_datetime.isoformat(),
                "arrives": leg.arrival_datetime.isoformat(),
                "duration_minutes": leg.duration,
            }
        )
    return {
        "from": legs[0]["from"] if legs else None,
        "to": legs[-1]["to"] if legs else None,
        "date": legs[0]["departs"][:10] if legs else None,
        "stops": result.stops,
        "duration_minutes": result.duration,
        "price_at_this_step": result.price,
        "currency": result.currency,
        "legs": legs,
    }


def normalize_itinerary(result: Any) -> dict:
    """One search result to a plain dict, whatever the trip shape.

    `fli` returns a bare FlightResult for a one-way trip and a tuple of them for a
    round trip or multi-city trip, one per segment. Every element of that tuple
    carries a price, and those prices are NOT per-segment fares - they are the
    running total for the itinerary as it stood at that point in Google's
    selection flow. Verified live on 2026-08-10: a LIS-JFK-LIS round trip came
    back as (490.0, 490.0) EUR against a 442.0 one-way, and a four-segment
    LIS-PHX-SFO-LAX-LIS trip came back as tuples like
    (1577.0, 1577.0, 1577.0, 1595.0) where only the last element moves with the
    final leg chosen.

    So the itinerary price is the LAST element's price. `fli` itself agrees:
    `SearchFlights.get_booking_options` builds its booking token from
    `results[-1].price`, which is the number Google is asked to honour.

    Summing the elements would roughly quadruple the price of a four-leg trip.
    Taking the first would report a total that ignores the return leg actually
    picked. Neither is the fare.
    """
    segments = [_normalize_segment(r) for r in (result if isinstance(result, tuple) else (result,))]
    total = segments[-1]["price_at_this_step"]
    return {
        "price": total,
        "currency": segments[-1]["currency"],
        "trip_shape": trip_shape(
            [{"origin": s["from"], "destination": s["to"], "date": s["date"]} for s in segments]
        ),
        "stops": sum(s["stops"] for s in segments if s["stops"] is not None),
        "duration_minutes": sum(s["duration_minutes"] for s in segments if s["duration_minutes"]),
        "segments": segments,
    }


def _canary_is_healthy(currency: str, searcher: Callable[[dict, str, int], list]) -> tuple[bool, str]:
    """Is the scraper alive at all? Run a dense control route and see.

    Returns (healthy, detail). Any failure to answer counts as unhealthy - the
    point of the canary is to refuse to call an empty result genuine unless
    something else came back priced at the same moment.
    """
    origin, destination = canary_route()
    date = (now_utc() + timedelta(days=canary_lead_days())).strftime("%Y-%m-%d")
    query = {"origin": origin, "destination": destination, "date": date, "sort": "cheapest"}
    try:
        results = searcher(query, currency, 3)
    except FlightSearchError as exc:
        return False, f"canary {origin}-{destination} {date} failed: {exc.kind}: {exc.message}"
    except Exception as exc:  # noqa: BLE001
        return False, f"canary {origin}-{destination} {date} raised {type(exc).__name__}: {exc}"
    priced = [r for r in results or [] if getattr(r, "price", None) is not None]
    if not priced:
        return False, f"canary {origin}-{destination} {date} returned no priced flights"
    return True, f"canary {origin}-{destination} {date} returned {len(priced)} priced flights"


_CANARY_CACHE: dict[str, tuple[bool, str]] = {}


def canary_check(currency: str, searcher: Callable[[dict, str, int], list]) -> tuple[bool, str]:
    """Cached per process. One check_prices run asks Google about the control route once."""
    if currency not in _CANARY_CACHE:
        _CANARY_CACHE[currency] = _canary_is_healthy(currency, searcher)
    return _CANARY_CACHE[currency]


def reset_canary_cache() -> None:
    _CANARY_CACHE.clear()


def interpret_results(
    raw: Iterable | None,
    currency: str,
    searcher: Callable[[dict, str, int], list],
    limit: int = 5,
) -> dict:
    """The whole empty-versus-broken decision, in one place.

    Raises FlightSearchError for every outcome that is not usable data, and
    returns {"status": "empty"} only when a live canary says the scraper works.
    """
    rows = list(raw or [])
    if not rows:
        healthy, detail = canary_check(currency, searcher)
        if not healthy:
            raise FlightSearchError(
                "scraper_error",
                "no flights came back AND the control route is also empty - treat this as a broken "
                "scraper, not an empty route. Do not report 'no flights' or 'no price change'.",
                detail,
            )
        return {"status": "empty", "flights": [], "currency": currency, "canary": detail}

    flights = [normalize_itinerary(r) for r in rows]
    priced = [f for f in flights if f["price"] is not None]
    if not priced:
        raise FlightSearchError(
            "unpriced",
            f"{len(flights)} itineraries came back and not one carried a price - nothing here is "
            "trackable and the number you would report does not exist. Premium cabins on a "
            "multi-passenger round trip are the predictable case: Google expects a specific "
            "outbound and return to be picked before it quotes a fare.",
        )

    # Every segment's currency is checked, not just the one the total came off.
    # A mixed-currency itinerary would produce a total that means nothing.
    wrong = sorted(
        {
            (c or "none")
            for f in priced
            for c in [f["currency"]] + [s["currency"] for s in f["segments"] if s["price_at_this_step"] is not None]
            if (c or "").upper() != currency
        }
    )
    if wrong:
        raise FlightSearchError(
            "currency_mismatch",
            f"asked Google for {currency} and it answered in {', '.join(wrong)} - these prices are not "
            "comparable with the recorded history, so they are not being used",
        )

    priced.sort(key=lambda f: f["price"])
    return {
        "status": "ok",
        "currency": currency,
        "count": len(priced),
        "cheapest_price": priced[0]["price"],
        "flights": priced[:limit],
    }


# ---------------------------------------------------------------------------
# The live searchers
# ---------------------------------------------------------------------------


def live_flight_searcher(query: dict, currency: str, limit: int) -> list:
    fli = _load_fli()
    filters = build_flight_filters(fli, query, currency)
    # top_n is the expansion breadth for multi-leg trips: how many outbound
    # candidates get a follow-up request asking Google for the next leg. Cost is
    # roughly top_n ** (legs - 1) requests, so the default stays small. A
    # four-leg trip at top_n=2 took 90 seconds live; at top_n=5 it would be
    # thirty-one requests and several minutes.
    top_n = max(1, int(query.get("top_n") or default_top_n()))
    results = _call_upstream(fli.SearchFlights().search, filters, top_n=top_n, currency=currency)
    return list(results or [])


def live_date_searcher(query: dict, currency: str) -> list:
    fli = _load_fli()
    filters = build_date_filters(fli, query, currency)
    results = _call_upstream(fli.SearchDates().search, filters, currency=currency)
    return list(results or [])


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def describe_query(query: dict) -> dict:
    legs = normalize_legs(query)
    return {
        "trip_shape": trip_shape(legs),
        "legs": legs,
        "cabin": query.get("cabin", "economy"),
        "adults": int(query.get("adults", 1)),
    }


def search_flights(query: dict, currency: str | None = None, limit: int = 5, searcher=None) -> dict:
    """One-way, round trip or multi-city, decided by the legs in the query."""
    currency = (currency or default_currency()).upper()
    searcher = searcher or live_flight_searcher
    normalize_legs(query)  # fail on a bad query before spending a request
    raw = searcher(query, currency, limit)
    out = interpret_results(raw, currency, searcher, limit=limit)
    out["query"] = describe_query(query)
    return out


def search_dates(query: dict, currency: str | None = None, searcher=None, flight_searcher=None) -> dict:
    """Cheapest day across a range. Same empty-versus-broken rule as search_flights."""
    currency = (currency or default_currency()).upper()
    searcher = searcher or live_date_searcher
    flight_searcher = flight_searcher or live_flight_searcher
    raw = list(searcher(query, currency) or [])

    if not raw:
        healthy, detail = canary_check(currency, flight_searcher)
        if not healthy:
            raise FlightSearchError(
                "scraper_error",
                "the date grid came back empty AND the control route is also empty - treat this as a "
                "broken scraper, not a route with no prices",
                detail,
            )
        return {"status": "empty", "days": [], "currency": currency, "canary": detail}

    days = []
    for point in raw:
        dates = [d.strftime("%Y-%m-%d") for d in point.date]
        days.append(
            {
                "date": dates[0],
                "return_date": dates[1] if len(dates) > 1 else None,
                "price": point.price,
                "currency": point.currency,
            }
        )
    priced = [d for d in days if d["price"] is not None]
    if not priced:
        raise FlightSearchError(
            "unpriced", f"{len(days)} days came back and none of them carried a price"
        )
    wrong = sorted({(d["currency"] or "none") for d in priced if (d["currency"] or "").upper() != currency})
    if wrong:
        raise FlightSearchError(
            "currency_mismatch",
            f"asked Google for {currency} and it answered in {', '.join(wrong)}",
        )

    cheapest = min(priced, key=lambda d: d["price"])
    dearest = max(priced, key=lambda d: d["price"])
    return {
        "status": "ok",
        "currency": currency,
        "days": sorted(priced, key=lambda d: d["date"]),
        "cheapest": cheapest,
        "dearest": dearest,
        "spread": round(dearest["price"] - cheapest["price"], 2),
        "query": {
            "origin": query["origin"].upper(),
            "destination": query["destination"].upper(),
            "from_date": query["from_date"],
            "to_date": query["to_date"],
        },
    }


# ---------------------------------------------------------------------------
# Flexible windows
# ---------------------------------------------------------------------------


def _window(spec: str, label: str) -> tuple[str, str]:
    """'2026-12-20:2026-12-23' to a (first, last) pair. A bare date is a one-day window."""
    parts = [p.strip() for p in (spec or "").split(":") if p.strip()]
    if len(parts) == 1:
        parts = [parts[0], parts[0]]
    if len(parts) != 2:
        raise FlightSearchError(
            "bad_request", f"{label} must be YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD, got '{spec}'"
        )
    first, last = _check_date(parts[0], label), _check_date(parts[1], label)
    if last < first:
        first, last = last, first
    return first, last


def _days(window: tuple[str, str]) -> list[str]:
    start = datetime.strptime(window[0], "%Y-%m-%d")
    end = datetime.strptime(window[1], "%Y-%m-%d")
    span = (end - start).days
    if span > 60:
        raise FlightSearchError(
            "bad_request", f"a {span}-day window is too wide to search; keep it to 60 days or fewer"
        )
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(span + 1)]


def live_round_trip_calendar(query: dict, currency: str, duration: int) -> list:
    """Google's calendar grid for a round trip of a fixed length.

    Returns at most one (outbound, return) pair per call - the cheapest pair in
    the window at that trip length. Verified live: a one-way grid returns a price
    per day, but the round-trip grid answers with a single best pair. That is why
    a flexible round-trip search sweeps trip LENGTHS rather than days.
    """
    fli = _load_fli()
    out_window = query["out_window"]
    origin, destination = query["origin"], query["destination"]
    first_out = out_window[0]
    back = (datetime.strptime(first_out, "%Y-%m-%d") + timedelta(days=duration)).strftime("%Y-%m-%d")
    filters = fli.DateSearchFilters(
        trip_type=fli.TripType.ROUND_TRIP,
        passenger_info=fli.PassengerInfo(
            adults=int(query.get("adults", 1)), children=int(query.get("children", 0))
        ),
        flight_segments=[
            fli.FlightSegment(
                departure_airport=_airports(fli, origin, "origin"),
                arrival_airport=_airports(fli, destination, "destination"),
                travel_date=first_out,
            ),
            fli.FlightSegment(
                departure_airport=_airports(fli, destination, "destination"),
                arrival_airport=_airports(fli, origin, "origin"),
                travel_date=back,
            ),
        ],
        seat_type=_enum(fli.SeatType, CABINS, query.get("cabin", "economy"), "cabin"),
        stops=_enum(fli.MaxStops, MAX_STOPS, query.get("max_stops", "any"), "max_stops"),
        price_limit=_price_limit(fli, query, currency),
        airlines=_airlines(fli, query.get("airlines")),
        from_date=out_window[0],
        to_date=out_window[1],
        duration=duration,
    )
    results = _call_upstream(fli.SearchDates().search, filters, currency=currency)
    return list(results or [])


def search_flexible(query: dict, currency: str | None = None, calendar=None, flight_searcher=None) -> dict:
    """Cheapest round trips across an outbound window and a return window.

    Sweeps trip lengths rather than day pairs. Every trip length that can land
    both ends inside the two windows costs one calendar request, and Google
    answers each with the cheapest pair at that length. A four-day outbound
    window against a four-day return window is seven requests, not sixteen
    searches.

    These are calendar-grid prices, which is what Google shows before you pick
    flights. Run search_flights on a promising pair for real itineraries.
    """
    currency = (currency or default_currency()).upper()
    calendar = calendar or live_round_trip_calendar
    flight_searcher = flight_searcher or live_flight_searcher

    out_window = _window(query["out_window"], "out_window")
    back_window = _window(query["back_window"], "back_window")
    if back_window[0] < out_window[0]:
        raise FlightSearchError(
            "bad_request",
            f"the return window starts {back_window[0]}, before the outbound window opens {out_window[0]}",
        )

    first_out = datetime.strptime(out_window[0], "%Y-%m-%d")
    last_out = datetime.strptime(out_window[1], "%Y-%m-%d")
    first_back = datetime.strptime(back_window[0], "%Y-%m-%d")
    last_back = datetime.strptime(back_window[1], "%Y-%m-%d")
    shortest = max(1, (first_back - last_out).days)
    longest = (last_back - first_out).days
    if longest < shortest:
        raise FlightSearchError("bad_request", "no trip length fits between those two windows")

    inner = dict(query)
    inner["out_window"] = out_window
    options: list[dict] = []
    failures: list[dict] = []
    for duration in range(shortest, longest + 1):
        try:
            points = calendar(inner, currency, duration)
        except FlightSearchError as exc:
            failures.append({"nights": duration, "error_kind": exc.kind, "error": exc.message})
            continue
        for point in points:
            dates = [d.strftime("%Y-%m-%d") for d in point.date]
            if len(dates) < 2:
                continue
            if not (out_window[0] <= dates[0] <= out_window[1]):
                continue
            if not (back_window[0] <= dates[1] <= back_window[1]):
                continue
            if point.price is None:
                continue
            if (point.currency or "").upper() != currency:
                raise FlightSearchError(
                    "currency_mismatch",
                    f"asked Google for {currency} and the calendar answered in {point.currency}",
                )
            options.append(
                {
                    "out_date": dates[0],
                    "back_date": dates[1],
                    "nights": duration,
                    "price": point.price,
                    "currency": point.currency,
                }
            )

    if not options:
        # Same rule as everywhere else: prove the scraper is alive before
        # calling an empty answer an answer.
        healthy, detail = canary_check(currency, flight_searcher)
        if not healthy:
            raise FlightSearchError(
                "scraper_error",
                "no date pair came back for any trip length AND the control route is also empty - "
                "treat this as a broken scraper, not a route with no fares",
                detail,
            )
        if failures:
            raise FlightSearchError(
                "empty_window",
                f"every trip length either failed or returned nothing across {len(range(shortest, longest + 1))} "
                "lengths, while the control route is healthy",
                failures,
            )
        return {
            "status": "empty",
            "options": [],
            "currency": currency,
            "canary": detail,
            "searched_nights": [shortest, longest],
        }

    options.sort(key=lambda o: o["price"])
    # One row per date pair: two trip lengths can resolve to the same pair.
    seen = set()
    unique = []
    for option in options:
        key = (option["out_date"], option["back_date"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(option)

    return {
        "status": "ok",
        "currency": currency,
        "source": "google calendar grid - indicative prices, run search_flights on a pair for real itineraries",
        "cheapest": unique[0],
        "options": unique,
        "spread": round(unique[-1]["price"] - unique[0]["price"], 2),
        "searched_nights": [shortest, longest],
        "failures": failures,
        "query": {
            "origin": query["origin"].upper(),
            "destination": query["destination"].upper(),
            "out_window": list(out_window),
            "back_window": list(back_window),
        },
    }


# ---------------------------------------------------------------------------
# Trip planning: multi-city across flexible windows
# ---------------------------------------------------------------------------


def _split_nights(total: int, cities: list[str], fixed: dict) -> list[int]:
    """Nights per city. Named cities keep their nights; the rest share what is left."""
    for city, nights in fixed.items():
        if city not in cities:
            raise FlightSearchError("bad_request", f"nights given for '{city}', which is not in the visit list")
        if nights < 1:
            raise FlightSearchError("bad_request", f"nights for '{city}' must be at least 1")
    spoken_for = sum(fixed.get(city, 0) for city in cities)
    free_cities = [c for c in cities if c not in fixed]
    remaining = total - spoken_for
    if remaining < len(free_cities):
        raise FlightSearchError(
            "bad_request",
            f"a {total}-night trip cannot cover {len(cities)} cities with {spoken_for} nights already "
            f"assigned - at least one night each is needed",
        )
    out = []
    for index, city in enumerate(cities):
        if city in fixed:
            out.append(fixed[city])
            continue
        share = remaining // len(free_cities)
        # The last free city absorbs the remainder rather than dropping days.
        if city == free_cities[-1]:
            share = remaining - share * (len(free_cities) - 1)
        out.append(share)
    return out


def build_itinerary_legs(origin: str, cities: list[str], out_date: str, nights: list[int]) -> list[dict]:
    hops = [origin] + cities + [origin]
    legs = []
    current = datetime.strptime(out_date, "%Y-%m-%d")
    for index in range(len(hops) - 1):
        legs.append(
            {
                "origin": hops[index],
                "destination": hops[index + 1],
                "date": current.strftime("%Y-%m-%d"),
            }
        )
        if index < len(nights):
            current = current + timedelta(days=nights[index])
    return legs


def plan_trip(query: dict, currency: str | None = None, searcher=None, flexible=None) -> dict:
    """Price a multi-city trip across flexible outbound and return windows.

    The expensive part is a real multi-city search: at two legs of expansion
    breadth it is roughly `top_n ** (legs - 1)` requests and took ninety seconds
    live for a four-leg trip. A four-day outbound window against a four-day
    return window is sixteen date pairs, which would be twenty-four minutes of
    scraping for one question.

    So the date pairs are ranked first with the cheap calendar grid - a plain
    return to the first city on the list, one request per trip length - and only
    the best few get a real itinerary search. **That ranking is a heuristic.** It
    prices a simple return, not the trip. It is used to choose which dates are
    worth searching, never as the price of anything, and every price reported
    back comes from a real multi-city search.
    """
    currency = (currency or default_currency()).upper()
    searcher = searcher or live_flight_searcher
    flexible = flexible or search_flexible

    origin = ",".join(_codes(query["origin"], "origin"))
    cities = [c.strip().upper() for c in (query.get("visit") or "").split(",") if c.strip()]
    if not cities:
        raise FlightSearchError("bad_request", "visit must list at least one city, e.g. 'PHX,SFO,LAX'")
    for city in cities:
        _codes(city, "visit")

    out_window = _window(query["out_window"], "out_window")
    back_window = _window(query["back_window"], "back_window")
    budget = max(1, int(query.get("max_searches") or max_plan_searches()))

    ranking = flexible(
        {
            "origin": origin,
            "destination": cities[0],
            "out_window": query["out_window"],
            "back_window": query["back_window"],
            "adults": query.get("adults", 1),
            "children": query.get("children", 0),
            "cabin": query.get("cabin", "economy"),
            "max_stops": query.get("max_stops", "any"),
        },
        currency=currency,
    )
    pairs = ranking.get("options") or []
    if not pairs:
        # Fall back to the corners of the windows rather than giving up: the
        # calendar being thin is not a reason to refuse to price a trip.
        out_days, back_days = _days(out_window), _days(back_window)
        pairs = [
            {"out_date": out_days[0], "back_date": back_days[0], "price": None, "currency": currency},
            {"out_date": out_days[-1], "back_date": back_days[-1], "price": None, "currency": currency},
        ]

    fixed_nights = query.get("nights") or {}
    candidates = []
    for pair in pairs[:budget]:
        total_nights = (
            datetime.strptime(pair["back_date"], "%Y-%m-%d")
            - datetime.strptime(pair["out_date"], "%Y-%m-%d")
        ).days
        nights = _split_nights(total_nights, cities, fixed_nights)
        candidates.append(
            {
                "out_date": pair["out_date"],
                "back_date": pair["back_date"],
                "total_nights": total_nights,
                "nights_by_city": dict(zip(cities, nights)),
                "indicative_price": pair.get("price"),
                "legs": build_itinerary_legs(origin, cities, pair["out_date"], nights),
            }
        )

    priced = []
    failures = []
    for candidate in candidates:
        leg_query = {
            "legs": candidate["legs"],
            "adults": query.get("adults", 1),
            "children": query.get("children", 0),
            "cabin": query.get("cabin", "economy"),
            "max_stops": query.get("max_stops", "any"),
            "airlines": query.get("airlines"),
            "max_price": query.get("max_price"),
            "top_n": query.get("top_n"),
            "sort": "cheapest",
        }
        try:
            result = search_flights(leg_query, currency=currency, limit=3, searcher=searcher)
        except FlightSearchError as exc:
            failures.append({**{k: candidate[k] for k in ("out_date", "back_date")},
                             "error_kind": exc.kind, "error": exc.message})
            continue
        if result["status"] != "ok":
            failures.append({**{k: candidate[k] for k in ("out_date", "back_date")},
                             "error_kind": "empty_itinerary",
                             "error": "no itinerary came back for these dates while the scraper is healthy"})
            continue
        priced.append(
            {
                "out_date": candidate["out_date"],
                "back_date": candidate["back_date"],
                "total_nights": candidate["total_nights"],
                "nights_by_city": candidate["nights_by_city"],
                "price": result["cheapest_price"],
                "currency": result["currency"],
                "legs": candidate["legs"],
                "best": result["flights"][0],
            }
        )

    if not priced:
        raise FlightSearchError(
            "no_itinerary",
            f"none of the {len(candidates)} date combinations produced a bookable itinerary. This is "
            "an error, not an answer: do not report it as 'no flights'.",
            failures,
        )

    priced.sort(key=lambda p: p["price"])
    return {
        "status": "ok",
        "currency": currency,
        "route": " - ".join([origin] + cities + [origin]),
        "cheapest": priced[0],
        "options": priced,
        "searched": len(candidates),
        "skipped": max(0, len(pairs) - len(candidates)),
        "failures": failures,
        "date_ranking": {
            "method": "round-trip calendar grid to the first city, used to choose dates only",
            "considered": len(pairs),
        },
        "query": {
            "origin": origin,
            "visit": cities,
            "out_window": list(out_window),
            "back_window": list(back_window),
            "nights_fixed": fixed_nights,
        },
    }


# ---------------------------------------------------------------------------
# The tracked-route store
# ---------------------------------------------------------------------------


def empty_store() -> dict:
    return {"schema": STORE_SCHEMA, "routes": []}


def load_store(path: pathlib.Path | None = None) -> dict:
    path = path or store_path()
    if not path.exists():
        return empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlightSearchError(
            "store_error",
            f"the tracked-route store at {path} is unreadable: {exc}. Nothing was checked - fix or "
            "move the file rather than letting the tracker run against an empty list.",
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("routes"), list):
        raise FlightSearchError("store_error", f"the store at {path} is not in the expected shape")
    return data


def save_store(store: dict, path: pathlib.Path | None = None) -> None:
    """Atomic: write a sibling temp file, then replace. A killed container never
    leaves a half-written store behind."""
    path = path or store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tracked-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(store, handle, indent=2, sort_keys=False)
            handle.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        raise FlightSearchError("store_error", f"could not write the store at {path}: {exc}") from exc


def route_id(query: dict) -> str:
    legs = normalize_legs(query)
    material = json.dumps(
        {
            "legs": legs,
            "cabin": query.get("cabin", "economy"),
            "adults": int(query.get("adults", 1)),
            "children": int(query.get("children", 0)),
            "max_stops": query.get("max_stops", "any"),
            "airlines": (query.get("airlines") or "").upper(),
        },
        sort_keys=True,
    )
    digest = hashlib.sha1(material.encode("utf-8")).hexdigest()[:6]
    stops = [legs[0]["origin"].split(",")[0]] + [leg["destination"].split(",")[0] for leg in legs]
    if trip_shape(legs) == "round_trip":
        stops = stops[:2]
    return f"{'-'.join(stops)}-{legs[0]['date']}-{digest}"


def describe_route(query: dict) -> str:
    legs = normalize_legs(query)
    shape = trip_shape(legs)
    if shape == "one_way":
        return f"{legs[0]['origin']} to {legs[0]['destination']} on {legs[0]['date']}"
    if shape == "round_trip":
        return (
            f"{legs[0]['origin']} to {legs[0]['destination']}, out {legs[0]['date']}, "
            f"back {legs[1]['date']}"
        )
    hops = " - ".join([legs[0]["origin"]] + [leg["destination"] for leg in legs])
    return f"{hops}, from {legs[0]['date']}"


def track_flight(query: dict, target_price: float, currency: str | None = None, label: str | None = None,
                 path: pathlib.Path | None = None) -> dict:
    """Register a route. A target price is required, deliberately.

    Without one there is no definition of "worth interrupting someone over", and
    the alternative policies (any drop, any drop over N percent) both produce
    daily noise on a volatile route. new-jaxity#499 names this as the default.
    """
    if target_price is None:
        raise FlightSearchError(
            "bad_request",
            "target_price is required - a tracked route with no target has no alert condition",
        )
    try:
        target_price = float(target_price)
    except (TypeError, ValueError) as exc:
        raise FlightSearchError("bad_request", f"target_price must be a number, got '{target_price}'") from exc
    if target_price <= 0:
        raise FlightSearchError("bad_request", "target_price must be greater than zero")

    currency = (currency or default_currency()).upper()
    legs = normalize_legs(query)

    store = load_store(path)
    rid = route_id(query)
    for existing in store["routes"]:
        if existing["id"] == rid:
            existing["target_price"] = target_price
            existing["currency"] = currency
            if label:
                existing["label"] = label
            existing["updated_utc"] = iso(now_utc())
            save_store(store, path)
            return {"status": "ok", "action": "updated", "route": existing}

    stored_query = {k: v for k, v in query.items() if v is not None}
    # Store the resolved legs, not the shorthand. A route tracked as
    # "LIS to JFK returning on the 20th" and one tracked as two explicit legs are
    # the same route, and a check months later should not depend on which spelling
    # someone used.
    stored_query.pop("origin", None)
    stored_query.pop("destination", None)
    stored_query.pop("date", None)
    stored_query.pop("return_date", None)
    stored_query["legs"] = legs

    route = {
        "id": rid,
        "label": label or describe_route(query),
        "trip_shape": trip_shape(legs),
        "created_utc": iso(now_utc()),
        "query": stored_query,
        "target_price": target_price,
        "currency": currency,
        "status": "new",
        "consecutive_errors": 0,
        "history": [],
        "last_alert": None,
        "last_error": None,
        "last_checked_utc": None,
    }
    store["routes"].append(route)
    save_store(store, path)
    return {"status": "ok", "action": "created", "route": route}


def list_tracked(path: pathlib.Path | None = None) -> dict:
    store = load_store(path)
    routes = []
    for route in store["routes"]:
        history = route.get("history", [])
        routes.append(
            {
                "id": route["id"],
                "label": route.get("label"),
                "trip_shape": route.get("trip_shape", "one_way"),
                "query": route.get("query"),
                "target_price": route.get("target_price"),
                "currency": route.get("currency"),
                "status": route.get("status"),
                "last_checked_utc": route.get("last_checked_utc"),
                "last_price": history[-1]["price"] if history else None,
                "first_price": history[0]["price"] if history else None,
                "points": len(history),
                "history": history,
                "last_error": route.get("last_error"),
                "last_alert": route.get("last_alert"),
            }
        )
    broken = [r for r in routes if r["status"] == "error"]
    return {
        "status": "ok",
        "store": str(path or store_path()),
        "count": len(routes),
        "broken_count": len(broken),
        "routes": routes,
    }


def remove_tracked(rid: str, path: pathlib.Path | None = None) -> dict:
    store = load_store(path)
    before = len(store["routes"])
    store["routes"] = [r for r in store["routes"] if r["id"] != rid]
    if len(store["routes"]) == before:
        raise FlightSearchError("not_found", f"no tracked route with id '{rid}'")
    save_store(store, path)
    return {"status": "ok", "action": "removed", "id": rid, "remaining": len(store["routes"])}


# ---------------------------------------------------------------------------
# check_prices
# ---------------------------------------------------------------------------


def _alert_due_for_error(route: dict, now: datetime) -> bool:
    """First failure shouts. After that the route stays quiet for a few days so a
    long outage does not become a daily notification, then shouts again."""
    if route.get("status") != "error":
        return True
    last = route.get("last_alert") or {}
    if last.get("kind") != "error":
        return True
    try:
        last_ts = datetime.fromisoformat(last["ts_utc"])
    except (KeyError, ValueError):
        return True
    return now - last_ts >= timedelta(days=error_repeat_days())


def evaluate_price(route: dict, price: float, now: datetime) -> dict | None:
    """Alert on a transition, not on a state. Pure - no I/O, no clock of its own.

    A price that sits below target for a week is one alert, not seven. A price
    that drops further below an already-alerted target is worth saying again.
    """
    target = route.get("target_price")
    if target is None or price > target:
        return None
    last = route.get("last_alert") or {}
    if last.get("kind") == "target_met" and price >= last.get("price", float("inf")):
        return None
    history = route.get("history", [])
    previous = history[-1]["price"] if history else None
    return {
        "kind": "target_met",
        "route_id": route["id"],
        "label": route.get("label"),
        "price": price,
        "currency": route.get("currency"),
        "target_price": target,
        "previous_price": previous,
        "ts_utc": iso(now),
    }


def _record_point(route: dict, price: float, now: datetime, simulated: bool = False) -> None:
    point = {"ts_utc": iso(now), "price": price, "currency": route.get("currency")}
    if simulated:
        point["simulated"] = True
    route.setdefault("history", []).append(point)
    cap = max_history_points()
    if len(route["history"]) > cap:
        route["history"] = route["history"][-cap:]


def check_prices(path: pathlib.Path | None = None, searcher=None, simulate_drop: dict | None = None,
                 simulate_failure: set | None = None, now: datetime | None = None) -> dict:
    """Poll every tracked route. Errors are reported, never swallowed.

    The return envelope is what the heartbeat gate reads. `status` is "error"
    whenever any route failed, even if others succeeded, because a partially
    broken tracker still needs a human to look.
    """
    searcher = searcher or live_flight_searcher
    now = now or now_utc()
    simulate_drop = simulate_drop or {}
    simulate_failure = simulate_failure or set()

    store = load_store(path)
    alerts: list[dict] = []
    errors: list[dict] = []
    summaries: list[dict] = []

    for route in store["routes"]:
        rid = route["id"]
        previous_status = route.get("status")
        currency = (route.get("currency") or default_currency()).upper()
        simulated = False

        try:
            if rid in simulate_failure or "all" in simulate_failure:
                raise FlightSearchError(
                    "scraper_error",
                    "simulated scraper failure (--simulate-failure) - this is what a real Google "
                    "response-shape change looks like from here",
                    "simulated",
                )
            if rid in simulate_drop:
                price = float(simulate_drop[rid])
                simulated = True
            else:
                raw = searcher(route["query"], currency, 5)
                result = interpret_results(raw, currency, searcher, limit=5)
                if result["status"] == "empty":
                    raise FlightSearchError(
                        "empty_route",
                        "this route returned no flights at all while the control route is healthy. "
                        "The scraper is fine, so the route itself is empty - it is not a price of zero "
                        "and it is not 'no change'.",
                        result.get("canary"),
                    )
                price = result["cheapest_price"]
        except FlightSearchError as exc:
            route["last_error"] = {"kind": exc.kind, "message": exc.message, "ts_utc": iso(now)}
            route["last_checked_utc"] = iso(now)
            route["consecutive_errors"] = int(route.get("consecutive_errors", 0)) + 1
            if _alert_due_for_error(route, now):
                alert = {
                    "kind": "error",
                    "route_id": rid,
                    "label": route.get("label"),
                    "error_kind": exc.kind,
                    "error": exc.message,
                    "consecutive_errors": route["consecutive_errors"],
                    "ts_utc": iso(now),
                }
                alerts.append(alert)
                route["last_alert"] = alert
            route["status"] = "error"
            errors.append({"route_id": rid, "error_kind": exc.kind, "error": exc.message})
            summaries.append({"id": rid, "status": "error", "error_kind": exc.kind})
            continue

        alert = evaluate_price(route, price, now)
        _record_point(route, price, now, simulated=simulated)
        route["last_checked_utc"] = iso(now)
        route["consecutive_errors"] = 0
        route["last_error"] = None
        route["status"] = "ok"

        if previous_status == "error":
            recovery = {
                "kind": "recovered",
                "route_id": rid,
                "label": route.get("label"),
                "price": price,
                "currency": currency,
                "ts_utc": iso(now),
            }
            alerts.append(recovery)
            route["last_alert"] = recovery
        if alert:
            if simulated:
                alert["simulated"] = True
            alerts.append(alert)
            route["last_alert"] = alert

        summaries.append(
            {
                "id": rid,
                "label": route.get("label"),
                "status": "ok",
                "price": price,
                "currency": currency,
                "target_price": route.get("target_price"),
                "simulated": simulated,
            }
        )

    save_store(store, path)
    return {
        "status": "error" if errors else "ok",
        "checked": len(store["routes"]),
        "alerts": alerts,
        "errors": errors,
        "routes": summaries,
        "ts_utc": iso(now),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _query_args(parser: argparse.ArgumentParser, with_date: bool = True, legs: bool = False,
                with_destination: bool = True) -> None:
    parser.add_argument("--from", dest="origin", required=not legs,
                        help="origin IATA code, or a comma-separated list for multi-airport")
    if with_destination:
        parser.add_argument("--to", dest="destination", required=not legs,
                            help="destination IATA code, or a comma-separated list")
    else:
        parser.set_defaults(destination=None)
    if with_date:
        parser.add_argument("--date", required=not legs, help="departure date, YYYY-MM-DD")
    if legs:
        parser.add_argument("--return-date", help="return date, YYYY-MM-DD - makes it a round trip")
        parser.add_argument("--leg", action="append", metavar="ORIGIN:DEST:DATE",
                            help="one leg of a multi-city trip, repeatable and in travel order. "
                                 "Replaces --from/--to/--date.")
        parser.add_argument("--top-n", type=int,
                            help="expansion breadth for multi-leg trips (default 2). Cost is roughly "
                                 "top_n ** (legs - 1) requests.")
    parser.add_argument("--adults", type=int, default=1)
    parser.add_argument("--children", type=int, default=0)
    parser.add_argument("--infants-in-seat", type=int, default=0)
    parser.add_argument("--infants-on-lap", type=int, default=0)
    parser.add_argument("--cabin", default="economy", choices=sorted(CABINS))
    parser.add_argument("--max-stops", default="any", choices=sorted(MAX_STOPS))
    parser.add_argument("--airlines", help="comma-separated IATA airline codes to restrict to")
    parser.add_argument("--max-price", type=int, help="price ceiling in the search currency")
    parser.add_argument("--max-duration-minutes", type=int)
    parser.add_argument("--max-layover-minutes", type=int)
    parser.add_argument("--depart-after", type=int, help="earliest departure hour, 0-24, local")
    parser.add_argument("--depart-before", type=int, help="latest departure hour, 0-24, local")
    parser.add_argument("--arrive-after", type=int, help="earliest arrival hour, 0-24, local")
    parser.add_argument("--arrive-before", type=int, help="latest arrival hour, 0-24, local")


def _parse_leg(spec: str) -> dict:
    parts = [p.strip() for p in (spec or "").split(":")]
    if len(parts) != 3 or not all(parts):
        raise FlightSearchError("bad_request", f"--leg wants ORIGIN:DEST:DATE, got '{spec}'")
    return {"origin": parts[0], "destination": parts[1], "date": parts[2]}


def _query_from_args(args, with_date: bool = True) -> dict:
    query = {
        "origin": args.origin,
        "destination": args.destination,
        "adults": args.adults,
        "children": args.children,
        "infants_in_seat": args.infants_in_seat,
        "infants_on_lap": args.infants_on_lap,
        "cabin": args.cabin,
        "max_stops": args.max_stops,
        "airlines": args.airlines,
        "max_price": args.max_price,
        "max_duration_minutes": args.max_duration_minutes,
        "max_layover_minutes": args.max_layover_minutes,
        "depart_after": args.depart_after,
        "depart_before": args.depart_before,
        "arrive_after": args.arrive_after,
        "arrive_before": args.arrive_before,
    }
    if with_date:
        query["date"] = args.date
    if getattr(args, "leg", None):
        if args.origin or args.destination or getattr(args, "date", None):
            raise FlightSearchError(
                "bad_request", "use --leg on its own, or --from/--to/--date - not both"
            )
        query["legs"] = [_parse_leg(spec) for spec in args.leg]
        query.pop("origin", None)
        query.pop("destination", None)
        query.pop("date", None)
    elif with_date and hasattr(args, "leg") and not args.origin:
        raise FlightSearchError("bad_request", "give --from, --to and --date, or one or more --leg")
    if getattr(args, "return_date", None):
        query["return_date"] = args.return_date
    if getattr(args, "top_n", None):
        query["top_n"] = args.top_n
    return {k: v for k, v in query.items() if v is not None}


def _parse_nights(spec: str | None) -> dict:
    out = {}
    for pair in [p.strip() for p in (spec or "").split(",") if p.strip()]:
        if "=" not in pair:
            raise FlightSearchError("bad_request", f"--nights wants CITY=N, got '{pair}'")
        city, _, nights = pair.partition("=")
        try:
            out[city.strip().upper()] = int(nights)
        except ValueError as exc:
            raise FlightSearchError("bad_request", f"'{nights}' is not a number of nights") from exc
    return out


def _parse_simulated(pairs: list[str] | None) -> dict:
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise FlightSearchError("bad_request", f"--simulate-drop wants ROUTE_ID=PRICE, got '{pair}'")
        rid, _, price = pair.partition("=")
        try:
            out[rid] = float(price)
        except ValueError as exc:
            raise FlightSearchError("bad_request", f"'{price}' is not a price") from exc
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--currency", help="ISO 4217 code requested from Google and asserted on the response")
    parser.add_argument("--store", help="path to the tracked-route store")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser(
        "search", help="search_flights - one-way, round trip (--return-date) or multi-city (--leg)"
    )
    _query_args(p_search, legs=True)
    p_search.add_argument("--sort", default="cheapest", choices=sorted(SORTS))
    p_search.add_argument("--limit", type=int, default=5)

    p_dates = sub.add_parser("dates", help="search_dates - cheapest day across a range, one-way")
    _query_args(p_dates, with_date=False)
    p_dates.add_argument("--from-date", required=True)
    p_dates.add_argument("--to-date", required=True)

    p_flex = sub.add_parser(
        "flexible", help="search_flexible - cheapest round trips across an outbound and a return window"
    )
    _query_args(p_flex, with_date=False)
    p_flex.add_argument("--out-window", required=True, metavar="DATE[:DATE]",
                        help="outbound window, e.g. 2026-12-20:2026-12-23")
    p_flex.add_argument("--back-window", required=True, metavar="DATE[:DATE]",
                        help="return window, e.g. 2027-01-05:2027-01-08")

    p_plan = sub.add_parser(
        "plan", help="plan_trip - a multi-city trip across flexible windows, priced for real"
    )
    _query_args(p_plan, with_date=False, with_destination=False)
    p_plan.add_argument("--visit", required=True, metavar="PHX,SFO,LAX",
                        help="cities to touch, in travel order")
    p_plan.add_argument("--out-window", required=True, metavar="DATE[:DATE]")
    p_plan.add_argument("--back-window", required=True, metavar="DATE[:DATE]")
    p_plan.add_argument("--nights", metavar="PHX=7,SFO=6",
                        help="nights in named cities; the rest split what is left")
    p_plan.add_argument("--max-searches", type=int,
                        help="ceiling on full itinerary searches (default 4). Each one is slow.")
    p_plan.add_argument("--top-n", type=int, help="expansion breadth per leg (default 2)")

    p_track = sub.add_parser("track", help="track_flight - register a route with a target price")
    _query_args(p_track, legs=True)
    p_track.add_argument("--target-price", type=float, required=True)
    p_track.add_argument("--label")

    p_check = sub.add_parser("check", help="check_prices - poll tracked routes and emit alerts")
    p_check.add_argument("--simulate-drop", action="append", metavar="ROUTE_ID=PRICE",
                         help="demo path: inject a price instead of asking Google")
    p_check.add_argument("--simulate-failure", action="append", metavar="ROUTE_ID",
                         help="demo path: force a scraper failure ('all' for every route)")

    sub.add_parser("list", help="list_tracked - tracked routes with price history")

    p_remove = sub.add_parser("remove", help="remove_tracked - stop tracking")
    p_remove.add_argument("route_id")

    return parser


def run_command(args) -> dict:
    path = pathlib.Path(args.store) if args.store else None
    currency = (args.currency or default_currency()).upper()

    if args.command == "search":
        query = _query_from_args(args)
        query["sort"] = args.sort
        return search_flights(query, currency=currency, limit=args.limit)
    if args.command == "dates":
        query = _query_from_args(args, with_date=False)
        query["from_date"] = args.from_date
        query["to_date"] = args.to_date
        return search_dates(query, currency=currency)
    if args.command == "flexible":
        query = _query_from_args(args, with_date=False)
        query["out_window"] = args.out_window
        query["back_window"] = args.back_window
        return search_flexible(query, currency=currency)
    if args.command == "plan":
        query = _query_from_args(args, with_date=False)
        query["visit"] = args.visit
        query["out_window"] = args.out_window
        query["back_window"] = args.back_window
        query["nights"] = _parse_nights(args.nights)
        if args.max_searches:
            query["max_searches"] = args.max_searches
        return plan_trip(query, currency=currency)
    if args.command == "track":
        return track_flight(_query_from_args(args), args.target_price, currency=currency,
                            label=args.label, path=path)
    if args.command == "check":
        return check_prices(
            path=path,
            simulate_drop=_parse_simulated(args.simulate_drop),
            simulate_failure=set(args.simulate_failure or []),
        )
    if args.command == "list":
        return list_tracked(path)
    if args.command == "remove":
        return remove_tracked(args.route_id, path)
    raise FlightSearchError("bad_request", f"unknown command '{args.command}'")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_command(args)
    except FlightSearchError as exc:
        print(json.dumps(exc.to_dict(), indent=2))
        return 1
    print(json.dumps(result, indent=2, default=str))
    # A run that found a broken route exits nonzero so a shell caller notices
    # without having to parse the JSON.
    return 1 if result.get("status") == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
