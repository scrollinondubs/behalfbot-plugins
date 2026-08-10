#!/usr/bin/env python3
"""flight_search_mcp.py - the six flight tools over MCP stdio.

A hand-rolled JSON-RPC loop rather than an SDK, for one reason: this repo's
plugin test suites run stdlib-only with no pip install (see
.github/workflows/plugin-tests.yml), and an SDK import at module level would
make the server untestable in CI. The protocol surface an stdio MCP server has
to answer is small enough that hand-rolling it costs less than the dependency.

Speaks newline-delimited JSON-RPC 2.0 on stdin/stdout. Handles `initialize`,
`notifications/initialized`, `tools/list`, `tools/call` and `ping`. Every log
line goes to stderr - anything on stdout that is not a JSON-RPC message breaks
the transport.

Failures are returned as tool results with `isError: true` and the same
`error_kind` envelope the CLI prints, never as an empty success. A model that
gets `{"status": "empty"}` back has been told, in the payload, that a live
control query confirmed the scraper is working.
"""

from __future__ import annotations

import json
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import flight_tools  # noqa: E402
from flight_tools import FlightSearchError  # noqa: E402

SERVER_NAME = "flight-search"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2025-06-18"

_QUERY_PROPERTIES = {
    "origin": {
        "type": "string",
        "description": "Origin IATA code, or a comma-separated list for a multi-airport origin (e.g. 'LIS' or 'LIS,OPO').",
    },
    "destination": {
        "type": "string",
        "description": "Destination IATA code, or a comma-separated list (e.g. 'JFK,EWR').",
    },
    "adults": {"type": "integer", "minimum": 1, "default": 1},
    "children": {"type": "integer", "minimum": 0, "default": 0},
    "infants_in_seat": {"type": "integer", "minimum": 0, "default": 0},
    "infants_on_lap": {"type": "integer", "minimum": 0, "default": 0},
    "cabin": {"type": "string", "enum": sorted(flight_tools.CABINS), "default": "economy"},
    "max_stops": {"type": "string", "enum": sorted(flight_tools.MAX_STOPS), "default": "any"},
    "airlines": {"type": "string", "description": "Comma-separated IATA airline codes to restrict the search to."},
    "max_price": {"type": "integer", "description": "Price ceiling in the search currency."},
    "max_duration_minutes": {"type": "integer", "description": "Longest acceptable total journey, in minutes."},
    "max_layover_minutes": {"type": "integer", "description": "Longest acceptable single layover, in minutes."},
    "depart_after": {"type": "integer", "minimum": 0, "maximum": 24, "description": "Earliest departure hour, local."},
    "depart_before": {"type": "integer", "minimum": 0, "maximum": 24, "description": "Latest departure hour, local."},
    "arrive_after": {"type": "integer", "minimum": 0, "maximum": 24, "description": "Earliest arrival hour, local."},
    "arrive_before": {"type": "integer", "minimum": 0, "maximum": 24, "description": "Latest arrival hour, local."},
    "currency": {"type": "string", "description": "ISO 4217 code requested from Google and asserted on the response."},
}


def _query_schema(extra: dict, required: list) -> dict:
    props = dict(_QUERY_PROPERTIES)
    props.update(extra)
    return {"type": "object", "properties": props, "required": required}


TOOLS = [
    {
        "name": "search_flights",
        "description": (
            "Search Google Flights for one-way itineraries on a route for a date. Returns priced "
            "itineraries sorted cheapest first. status=empty means a live control query confirmed the "
            "scraper works and the route really has nothing; any failure comes back as an error with an "
            "error_kind - never report 'no flights' on an error."
        ),
        "inputSchema": _query_schema(
            {
                "date": {"type": "string", "description": "Departure date, YYYY-MM-DD."},
                "sort": {"type": "string", "enum": sorted(flight_tools.SORTS), "default": "cheapest"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 5},
            },
            ["origin", "destination", "date"],
        ),
    },
    {
        "name": "search_dates",
        "description": (
            "Cheapest departure day across a date range, from Google's calendar grid. Use this before "
            "search_flights when the traveller's dates are flexible."
        ),
        "inputSchema": _query_schema(
            {
                "from_date": {"type": "string", "description": "First departure date to price, YYYY-MM-DD."},
                "to_date": {"type": "string", "description": "Last departure date to price, YYYY-MM-DD."},
            },
            ["origin", "destination", "from_date", "to_date"],
        ),
    },
    {
        "name": "track_flight",
        "description": (
            "Register a route for daily price monitoring. target_price is required: it is the alert "
            "condition, and without one every wobble in a volatile fare becomes a notification."
        ),
        "inputSchema": _query_schema(
            {
                "date": {"type": "string", "description": "Departure date, YYYY-MM-DD."},
                "target_price": {"type": "number", "description": "Alert when the cheapest fare is at or below this."},
                "label": {"type": "string", "description": "Human label for the alert, e.g. 'Christmas trip home'."},
            },
            ["origin", "destination", "date", "target_price"],
        ),
    },
    {
        "name": "check_prices",
        "description": (
            "Poll every tracked route once and return alerts. Alerts fire on transitions: a fare crossing "
            "its target, a fare dropping further below an already-alerted target, a route breaking, and a "
            "broken route recovering. status=error means at least one route could not be priced - say so "
            "out loud rather than reporting no change."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_tracked",
        "description": "Every tracked route with its target, current status and full price history.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "remove_tracked",
        "description": "Stop tracking a route by its id (get ids from list_tracked).",
        "inputSchema": {
            "type": "object",
            "properties": {"route_id": {"type": "string"}},
            "required": ["route_id"],
        },
    },
]


def _query(args: dict, date_keys: list) -> dict:
    keys = [
        "origin", "destination", "adults", "children", "infants_in_seat", "infants_on_lap",
        "cabin", "max_stops", "airlines", "max_price", "max_duration_minutes",
        "max_layover_minutes", "depart_after", "depart_before", "arrive_after", "arrive_before",
    ] + date_keys
    return {k: args[k] for k in keys if args.get(k) is not None}


def dispatch_tool(name: str, args: dict) -> dict:
    args = args or {}
    currency = args.get("currency")
    if name == "search_flights":
        query = _query(args, ["date"])
        if args.get("sort"):
            query["sort"] = args["sort"]
        return flight_tools.search_flights(query, currency=currency, limit=int(args.get("limit", 5)))
    if name == "search_dates":
        return flight_tools.search_dates(_query(args, ["from_date", "to_date"]), currency=currency)
    if name == "track_flight":
        return flight_tools.track_flight(
            _query(args, ["date"]),
            args.get("target_price"),
            currency=currency,
            label=args.get("label"),
        )
    if name == "check_prices":
        return flight_tools.check_prices()
    if name == "list_tracked":
        return flight_tools.list_tracked()
    if name == "remove_tracked":
        return flight_tools.remove_tracked(args.get("route_id", ""))
    raise FlightSearchError("bad_request", f"unknown tool '{name}'")


def call_tool(name: str, args: dict) -> dict:
    """Always an MCP tool result. isError carries the failure; the payload names it."""
    try:
        payload = dispatch_tool(name, args)
        is_error = payload.get("status") == "error"
    except FlightSearchError as exc:
        payload, is_error = exc.to_dict(), True
    except Exception as exc:  # noqa: BLE001 - an unhandled crash must still reach the caller as an error
        print(traceback.format_exc(), file=sys.stderr)
        payload = {
            "status": "error",
            "error_kind": "internal_error",
            "error": f"{type(exc).__name__}: {exc}",
        }
        is_error = True
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2, default=str)}],
        "isError": is_error,
    }


def handle(message: dict) -> dict | None:
    """One JSON-RPC message in, at most one response out. None for notifications."""
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        requested = params.get("protocolVersion") or DEFAULT_PROTOCOL
        result = {
            "protocolVersion": requested,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    elif method in ("notifications/initialized", "initialized"):
        return None
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = call_tool(params.get("name", ""), params.get("arguments") or {})
    elif method and method.startswith("notifications/"):
        return None
    else:
        if msg_id is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"method not found: {method}"},
        }

    if msg_id is None:
        return None
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def serve(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"[flight-search] dropping unparseable line: {exc}", file=sys.stderr)
            continue
        response = handle(message)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(serve())
