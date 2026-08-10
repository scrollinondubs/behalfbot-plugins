#!/usr/bin/env python3
"""demo_search.py - drive the plugin end to end over the real MCP transport.

This is the demo path, and it is also the acceptance harness. It speaks the same
stdio JSON-RPC to the same proxy that a chassis speaks, so what you see here is
what the agent sees - including the empty-result warning, which is the point.

It hits airbnb.com and the geocoders for real. Nothing here is mocked. The
mocked tests live in tests/ and are what CI runs.

Usage:
    python3 scripts/demo_search.py                       # Lisbon, next month, 2 adults
    python3 scripts/demo_search.py --location "Porto, Portugal" --max-price 120
    python3 scripts/demo_search.py --details 1234567890  # one listing, no search
    python3 scripts/demo_search.py --json                # raw payloads, no prose

Search only. There is no booking path in this plugin and there is not meant to
be one.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PROXY = PLUGIN_ROOT / "scripts" / "airbnb_mcp_proxy.py"
TIMEOUT_SECONDS = 120


class McpSession:
    """A minimal MCP stdio client. Writes a request, waits for its response."""

    def __init__(self, command: list[str]) -> None:
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._next_id = 0

    def _send(self, message: dict) -> None:
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict) -> dict:
        self._next_id += 1
        request_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        while True:
            line = self.proc.stdout.readline()
            if not line:
                stderr = self.proc.stderr.read()
                raise RuntimeError(f"server closed the connection.\n{stderr}")
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"{method} failed: {message['error']}")
                return message.get("result", {})

    def notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def close(self) -> None:
        try:
            self.proc.stdin.close()
        except (BrokenPipeError, ValueError):
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def open_session() -> McpSession:
    session = McpSession([sys.executable, str(PROXY)])
    session.request(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "accommodation-search-demo", "version": "0.1.0"},
        },
    )
    session.notify("notifications/initialized")
    return session


def call_tool(session: McpSession, name: str, arguments: dict) -> tuple[dict, list[str]]:
    """Returns (parsed payload, plain-text blocks that came back alongside it)."""
    result = session.request("tools/call", {"name": name, "arguments": arguments})
    payload: dict = {}
    notices: list[str] = []
    for block in result.get("content", []):
        text = block.get("text", "")
        try:
            parsed = json.loads(text)
        except ValueError:
            notices.append(text)
            continue
        if isinstance(parsed, dict):
            payload = parsed
        else:
            notices.append(text)
    return payload, notices


def default_dates() -> tuple[str, str]:
    checkin = dt.date.today() + dt.timedelta(days=30)
    return checkin.isoformat(), (checkin + dt.timedelta(days=3)).isoformat()


def price_of(listing: dict) -> str:
    price = listing.get("structuredDisplayPrice", {})
    for line in ("primaryLine", "secondaryLine"):
        label = price.get(line, {}).get("accessibilityLabel")
        if label:
            return label
    return "price not shown"


def describe(listing: dict) -> str:
    stay = listing.get("demandStayListing", {})
    name = stay.get("description") or listing.get("id", "unknown listing")
    rating = listing.get("avgRatingA11yLabel", "no rating")
    return f"{name}\n    {price_of(listing)} | {rating}\n    {listing.get('url', '')}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--location", default="Lisbon, Portugal")
    parser.add_argument("--checkin")
    parser.add_argument("--checkout")
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--max-price", type=int)
    parser.add_argument("--limit", type=int, default=5, help="listings to print")
    parser.add_argument("--details", help="skip the search, detail this listing id")
    parser.add_argument("--json", action="store_true", help="print raw payloads")
    args = parser.parse_args()

    checkin, checkout = default_dates()
    checkin = args.checkin or checkin
    checkout = args.checkout or checkout

    session = open_session()
    try:
        if args.details:
            payload, notices = call_tool(
                session,
                "airbnb_listing_details",
                {"id": args.details, "checkin": checkin, "checkout": checkout,
                 "adults": args.adults},
            )
            return report_details(payload, notices, args)

        search_args = {
            "location": args.location,
            "checkin": checkin,
            "checkout": checkout,
            "adults": args.adults,
        }
        if args.max_price:
            search_args["maxPrice"] = args.max_price

        payload, notices = call_tool(session, "airbnb_search", search_args)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Search: {args.location}, {checkin} to {checkout}, {args.adults} adults")
            if args.max_price:
                print(f"Ceiling: {args.max_price} per night")
            print()
            for notice in notices:
                print(notice + "\n")
            listings = payload.get("searchResults") or []
            print(f"{len(listings)} listing(s) returned. Showing up to {args.limit}:\n")
            for listing in listings[: args.limit]:
                print("  - " + describe(listing) + "\n")
            print(f"Search URL: {payload.get('searchUrl', 'n/a')}")

        listings = payload.get("searchResults") or []
        if not listings:
            return 2

        first_id = listings[0].get("id")
        if not first_id:
            return 0
        print(f"\nDetails for the first result ({first_id}):\n")
        details_payload, details_notices = call_tool(
            session,
            "airbnb_listing_details",
            {"id": first_id, "checkin": checkin, "checkout": checkout, "adults": args.adults},
        )
        return report_details(details_payload, details_notices, args)
    finally:
        session.close()


def report_details(payload: dict, notices: list[str], args) -> int:
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for notice in notices:
            print(notice + "\n")
        for section in payload.get("details") or []:
            title = section.get("title") or section.get("id") or "section"
            body = json.dumps(section, indent=2)
            print(f"  [{title}] {body[:600]}{'...' if len(body) > 600 else ''}\n")
        print(f"Listing URL: {payload.get('listingUrl', 'n/a')}")
    return 0 if payload.get("details") else 2


if __name__ == "__main__":
    raise SystemExit(main())
