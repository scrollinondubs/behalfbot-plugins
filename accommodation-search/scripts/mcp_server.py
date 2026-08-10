#!/usr/bin/env python3
"""MCP stdio server exposing three supplier-neutral accommodation tools.

Newline-delimited JSON-RPC on stdin and stdout, which is the MCP stdio
transport. Python standard library only - no SDK, no pip install, nothing that
resolves a package at install time on somebody's machine.

The tool schemas below are the plugin's public surface and they are deliberately
free of any supplier's vocabulary. `city_code`, `check_in`, `max_price`. Not
`hotelIds`, not `cityCode`, not `offerId`. A second supplier arrives by adding a
value to the `supplier` enum and a module behind it, and every existing caller
keeps working. There is a test that fails if a supplier's dialect leaks into a
schema, because this is the sort of constraint that holds until the afternoon
somebody is in a hurry.

Every failure - including a search that returned nothing - comes back with
isError true and a structured payload naming the failure kind. There is no code
path here that answers a zero-result search with an empty list.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from accommodation_errors import AccommodationError  # noqa: E402
from amadeus_client import REDACTOR, AmadeusClient  # noqa: E402
from amadeus_supplier import AmadeusSupplier  # noqa: E402
from supplier import (  # noqa: E402
    IMPLEMENTED_SUPPLIERS,
    MAX_RESULTS_CEILING,
    MAX_RESULTS_REASON,
    RESERVED_SUPPLIERS,
    Place,
    SearchQuery,
    Stay,
    parse_date,
    split_id,
    unsupported_supplier,
)

SERVER_NAME = "accommodation-search"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

INVENTORY_WARNING = (
    "GDS and chain hotel inventory. Hotels, not apartments. Short-let flats, "
    "Airbnb-style listings and non-chain properties are not in this supplier, "
    "so nothing here can be read as a complete picture of a city's "
    "accommodation."
)

SUPPLIER_PROPERTY = {
    "type": "string",
    "enum": list(IMPLEMENTED_SUPPLIERS),
    "default": IMPLEMENTED_SUPPLIERS[0],
    "description": (
        "Which supplier answers. Implemented: "
        + ", ".join(IMPLEMENTED_SUPPLIERS)
        + ". Reserved and not yet implemented: "
        + ", ".join(sorted(RESERVED_SUPPLIERS))
        + " - asking for a reserved one returns a clear error rather than "
        "falling back silently, because the inventory differs and a silent "
        "fallback would be a wrong answer about what was searched."
    ),
}

STAY_PROPERTIES = {
    "check_in": {
        "type": "string",
        "description": "First night, YYYY-MM-DD. Resolve relative dates before calling.",
    },
    "check_out": {
        "type": "string",
        "description": "Departure day, YYYY-MM-DD. A one-night stay checks out the day after check-in.",
    },
    "adults": {"type": "integer", "minimum": 1, "maximum": 9, "default": 1},
    "rooms": {"type": "integer", "minimum": 1, "maximum": 9, "default": 1},
}

TOOLS = [
    {
        "name": "search_accommodation",
        "description": (
            "Find places to stay in a city or around a point, priced for a date "
            "range and a party size. " + INVENTORY_WARNING + " Search only: it "
            "never books anything. A search that finds nothing returns an "
            "error, not an empty list."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "supplier": SUPPLIER_PROPERTY,
                "city_code": {
                    "type": "string",
                    "description": (
                        "Three-letter IATA city code - LIS Lisbon, LON London, "
                        "NYC New York. Either this or a latitude/longitude pair."
                    ),
                },
                "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                "radius_km": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 300,
                    "default": 5,
                    "description": "How far from the city centre or the given point to look.",
                },
                **STAY_PROPERTIES,
                "max_price": {
                    "type": "number",
                    "description": (
                        "Ceiling on the total for the stay. Needs a currency. "
                        "Applied by the supplier, so too tight a ceiling empties "
                        "the result before it gets here."
                    ),
                },
                "currency": {"type": "string", "description": "ISO code, e.g. EUR."},
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_RESULTS_CEILING,
                    "default": 10,
                    "description": "How many properties to price. " + MAX_RESULTS_REASON,
                },
                "amenities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Filter the property list, e.g. WIFI, PARKING, "
                        "SWIMMING_POOL, AIR_CONDITIONING, RESTAURANT, "
                        "FITNESS_CENTER, PETS_ALLOWED."
                    ),
                },
            },
            "required": ["check_in", "check_out"],
        },
    },
    {
        "name": "accommodation_details",
        "description": (
            "Everything known about one property: address, location, chain, "
            "guest ratings, and - when dates are given - amenities, policies "
            "and rates for those dates. " + INVENTORY_WARNING
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "string",
                    "description": (
                        "A property_id exactly as a search result returned it, "
                        "including the supplier prefix, e.g. 'amadeus:HLPAR266'."
                    ),
                },
                **STAY_PROPERTIES,
            },
            "required": ["property_id"],
        },
    },
    {
        "name": "list_accommodation_offers",
        "description": (
            "Every bookable rate for one property and one stay, cheapest first, "
            "with what each includes and how each cancels. Prices are "
            "indicative and expire - re-run before quoting one. Search only: "
            "the traveller books it themselves."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "string",
                    "description": "A property_id from a search result, e.g. 'amadeus:HLPAR266'.",
                },
                **STAY_PROPERTIES,
                "currency": {"type": "string", "description": "ISO code, e.g. EUR."},
                "all_rates": {
                    "type": "boolean",
                    "default": True,
                    "description": (
                        "True returns every rate the property publishes; false "
                        "returns only its cheapest."
                    ),
                },
            },
            "required": ["property_id", "check_in", "check_out"],
        },
    },
]


def build_supplier(name: str, env=None, stderr=None):
    if name not in IMPLEMENTED_SUPPLIERS:
        raise unsupported_supplier(name)
    client = AmadeusClient.from_env(env=env, stderr=stderr)
    return AmadeusSupplier(client)


def _stay_from(arguments: dict, required: bool) -> Stay | None:
    check_in = arguments.get("check_in")
    check_out = arguments.get("check_out")
    if not check_in and not check_out and not required:
        return None
    return Stay(
        check_in=parse_date(check_in, "check_in"),
        check_out=parse_date(check_out, "check_out"),
        adults=int(arguments.get("adults") or 1),
        rooms=int(arguments.get("rooms") or 1),
    )


def call_tool(name: str, arguments: dict, env=None, stderr=None) -> dict:
    """Run one tool and return its payload, or raise AccommodationError."""
    arguments = arguments or {}

    if name == "search_accommodation":
        supplier_name = arguments.get("supplier") or IMPLEMENTED_SUPPLIERS[0]
        supplier = build_supplier(supplier_name, env=env, stderr=stderr)
        query = SearchQuery(
            place=Place(
                city_code=arguments.get("city_code"),
                latitude=arguments.get("latitude"),
                longitude=arguments.get("longitude"),
                radius_km=int(arguments.get("radius_km") or 5),
            ),
            stay=_stay_from(arguments, required=True),
            max_price=arguments.get("max_price"),
            currency=arguments.get("currency"),
            max_results=int(arguments.get("max_results") or 10),
            amenities=tuple(arguments.get("amenities") or ()),
        )
        return supplier.search(query)

    if name == "accommodation_details":
        supplier_name, native_id = split_id(arguments.get("property_id"))
        supplier = build_supplier(supplier_name, env=env, stderr=stderr)
        return supplier.details(native_id, _stay_from(arguments, required=False))

    if name == "list_accommodation_offers":
        supplier_name, native_id = split_id(arguments.get("property_id"))
        supplier = build_supplier(supplier_name, env=env, stderr=stderr)
        return supplier.offers(
            native_id,
            _stay_from(arguments, required=True),
            currency=arguments.get("currency"),
            all_rates=arguments.get("all_rates", True),
        )

    raise AccommodationError(
        kind="BAD_REQUEST",
        message=f"Unknown tool '{name}'.",
        what_to_do=[f"Available tools: {', '.join(tool['name'] for tool in TOOLS)}."],
    )


def tool_result(payload: dict, is_error: bool = False, headline: str | None = None) -> dict:
    """The MCP tools/call result shape.

    Two content blocks when something went wrong: a plain-text headline first,
    because an agent that reads only the first block still has to see that this
    was a failure, and the JSON after it for anything that parses.
    """
    payload = REDACTOR.scrub(payload)
    blocks = []
    if headline:
        blocks.append({"type": "text", "text": REDACTOR.scrub(headline)})
    blocks.append({"type": "text", "text": json.dumps(payload, indent=2, default=str)})
    return {"content": blocks, "isError": is_error}


def error_result(error: AccommodationError) -> dict:
    headline_lines = [f"{error.kind}: {error.message}"]
    if error.what_to_do:
        headline_lines.append("")
        headline_lines.extend(f"- {step}" for step in error.what_to_do)
    return tool_result(error.to_payload(), is_error=True, headline="\n".join(headline_lines))


def handle(message: dict, env=None, stderr=None) -> dict | None:
    """One JSON-RPC message in, at most one response out. Notifications, which
    carry no id, get no response."""
    method = message.get("method")
    msg_id = message.get("id")

    if method == "initialize":
        params = message.get("params") or {}
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = message.get("params") or {}
        try:
            payload = call_tool(
                params.get("name"), params.get("arguments") or {}, env=env, stderr=stderr
            )
            result = tool_result(payload)
        except AccommodationError as error:
            result = error_result(error)
        except Exception as unexpected:  # noqa: BLE001
            result = error_result(
                AccommodationError(
                    kind="SUPPLIER_ERROR",
                    message=f"Unhandled failure in {params.get('name')}: {unexpected}",
                    what_to_do=[
                        "This is a bug in the plugin, not a supplier problem. "
                        "Report the tool name and arguments.",
                        "Do not report this to the traveller as a result about "
                        "availability.",
                    ],
                )
            )
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    if msg_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    out = sys.stdout
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except ValueError:
            out.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": "Parse error"},
                    }
                )
                + "\n"
            )
            out.flush()
            continue
        if not isinstance(message, dict):
            continue
        response = handle(message, stderr=sys.stderr)
        if response is not None:
            out.write(json.dumps(response, default=str) + "\n")
            out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
