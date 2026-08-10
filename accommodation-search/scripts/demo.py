#!/usr/bin/env python3
"""The demo path, and the live acceptance harness. One script, both jobs.

It talks to the MCP server the same way the agent does - a subprocess over
newline-delimited JSON-RPC on stdio - rather than importing the tool functions
directly. What you see on screen is therefore what the agent gets, including
the error blocks, rather than a prettier rehearsal of it.

With no credentials, `--fixtures` serves committed JSON instead of calling
anyone. Three sets ship: a search that works, a search that comes back empty,
and a search that dies on the monthly quota. Those are the three outcomes worth
seeing, and two of them are hard to produce on demand against a live account.

    python3 scripts/demo.py --fixtures happy --city LON
    python3 scripts/demo.py --fixtures empty --city LON
    python3 scripts/demo.py --fixtures quota --city LON

With credentials in the environment it calls Amadeus for real. Same flags, same
output, and the `data_source` line at the top of every result says which it was.

Exit codes: 0 for a result, 2 for a tool error, 1 for a problem with the demo
itself. So it works as a smoke check in a script and not only in front of a
camera.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SERVER = PLUGIN_ROOT / "scripts" / "mcp_server.py"
FIXTURE_SETS = {
    "happy": PLUGIN_ROOT / "tests" / "fixtures" / "happy",
    "empty": PLUGIN_ROOT / "tests" / "fixtures" / "empty",
    "quota": PLUGIN_ROOT / "tests" / "fixtures" / "quota",
}


class Server:
    """One MCP server subprocess, spoken to over stdio."""

    def __init__(self, env: dict) -> None:
        self.process = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            env=env,
            text=True,
            bufsize=1,
        )
        self._next_id = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        request = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            request["params"] = params
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise SystemExit("the MCP server exited without answering")
        return json.loads(line)

    def close(self) -> None:
        try:
            self.process.stdin.close()
        except (BrokenPipeError, ValueError):
            pass
        self.process.wait(timeout=10)


def money(offer: dict) -> str:
    price = offer.get("price") or {}
    total = price.get("total_for_stay") or "?"
    each = price.get("average_per_night")
    line = f"{price.get('currency') or ''} {total} total".strip()
    return f"{line} ({each}/night)" if each else line


def print_search(payload: dict) -> None:
    print(f"  source: {payload.get('data_source')}")
    print(f"  {payload.get('_coverage_note', '')}\n")
    for index, entry in enumerate(payload.get("results") or [], start=1):
        prop = entry["property"]
        print(f"  {index}. {prop['name']}  [{prop['property_id']}]")
        if prop.get("distance_km") is not None:
            print(f"     {prop['distance_km']}km from centre, chain {prop.get('chain_code')}")
        for offer in entry["offers"]:
            room = offer["room"]
            print(f"     {money(offer)} - {room.get('category') or 'room'}")
            cancellation = (offer["policies"].get("cancellation") or [{}])[0]
            if cancellation.get("description") or cancellation.get("deadline"):
                print(
                    f"     cancellation: "
                    f"{cancellation.get('description') or cancellation.get('deadline')}"
                )
        print()
    print(f"  {payload.get('inventory_note')}")
    usage = payload.get("usage") or {}
    print(
        f"  quota: {usage.get('supplier_calls_counted')} of "
        f"{usage.get('local_monthly_budget')} calls counted for {usage.get('month')}"
    )


def print_details(payload: dict) -> None:
    prop = payload["property"]
    print(f"  source: {payload.get('data_source')}")
    print(f"  {prop['name']}  [{prop['property_id']}]")
    print(f"  chain {prop.get('chain_code')}, {prop.get('country_code')}, {prop.get('coordinates')}")
    rating = payload.get("rating") or {}
    if rating.get("overall_rating") is not None:
        print(f"  rating {rating['overall_rating']}/100 from {rating.get('number_of_reviews')} reviews")
        for name, score in (rating.get("sentiments") or {}).items():
            print(f"     {name}: {score}")
    else:
        print(f"  rating unavailable: {rating.get('unavailable')} - {rating.get('detail')}")
    for offer in payload.get("rates") or []:
        print(f"  rate: {money(offer)} - {offer['room'].get('description')}")
    print(f"\n  {payload.get('inventory_note')}")


def print_offers(payload: dict) -> None:
    print(f"  source: {payload.get('data_source')}")
    print(f"  {payload['property']['name']}, {payload['stay']}\n")
    for offer in payload["offers"]:
        print(f"  {money(offer)}  [{offer['offer_id']}]")
        print(f"     {offer['room'].get('category')}, board {offer.get('board_type') or 'not stated'}")
        print(f"     payment {offer['policies'].get('payment_type')}")
    print(f"\n  {payload.get('_offer_lifetime_note')}")
    print(f"  {payload.get('booking_note')}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixtures", choices=sorted(FIXTURE_SETS), help="Serve committed JSON instead of calling the supplier.")
    parser.add_argument("--city", default="LON", help="IATA city code. LON London, NYC New York, LIS Lisbon.")
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--radius-km", type=int, default=5)
    parser.add_argument("--check-in", help="YYYY-MM-DD. Defaults to 30 days out.")
    parser.add_argument("--check-out", help="YYYY-MM-DD. Defaults to two nights.")
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--rooms", type=int, default=1)
    parser.add_argument("--max-price", type=float)
    parser.add_argument("--currency")
    parser.add_argument("--limit", type=int, default=5, help="How many properties to price.")
    parser.add_argument("--details", metavar="PROPERTY_ID", help="Detail one property, e.g. amadeus:MCLONGHM.")
    parser.add_argument("--offers", metavar="PROPERTY_ID", help="Every rate for one property.")
    parser.add_argument("--json", action="store_true", help="Print the raw tool payload.")
    args = parser.parse_args(argv[1:])

    check_in = args.check_in or (date.today() + timedelta(days=30)).isoformat()
    check_out = args.check_out or (date.fromisoformat(check_in) + timedelta(days=2)).isoformat()

    env = dict(os.environ)
    if args.fixtures:
        env["ACCOMMODATION_FIXTURE_DIR"] = str(FIXTURE_SETS[args.fixtures])
        print(f"FIXTURE MODE '{args.fixtures}': canned responses, nothing is being called.\n")
    elif not (env.get("AMADEUS_CLIENT_ID") and env.get("AMADEUS_CLIENT_SECRET")):
        print(
            "AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET are not set.\n"
            "Export them, or run with --fixtures happy to see the shape offline.",
            file=sys.stderr,
        )

    stay = {"check_in": check_in, "check_out": check_out, "adults": args.adults, "rooms": args.rooms}
    if args.details:
        tool, arguments, printer = "accommodation_details", {"property_id": args.details, **stay}, print_details
    elif args.offers:
        tool, arguments, printer = "list_accommodation_offers", {"property_id": args.offers, **stay}, print_offers
    else:
        tool, printer = "search_accommodation", print_search
        arguments = {
            **stay,
            "radius_km": args.radius_km,
            "max_results": args.limit,
            "currency": args.currency,
            "max_price": args.max_price,
        }
        if args.latitude is not None and args.longitude is not None:
            arguments.update({"latitude": args.latitude, "longitude": args.longitude})
        else:
            arguments["city_code"] = args.city
        arguments = {key: value for key, value in arguments.items() if value is not None}

    server = Server(env)
    try:
        server.call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                   "clientInfo": {"name": "accommodation-search-demo", "version": "0.1.0"}})
        response = server.call("tools/call", {"name": tool, "arguments": arguments})
    finally:
        server.close()

    result = response.get("result") or {}
    blocks = result.get("content") or []
    payload = json.loads(blocks[-1]["text"]) if blocks else {}

    print(f"== {tool}")
    if result.get("isError"):
        print(blocks[0]["text"] if len(blocks) > 1 else json.dumps(payload, indent=2))
        return 2
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        printer(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
