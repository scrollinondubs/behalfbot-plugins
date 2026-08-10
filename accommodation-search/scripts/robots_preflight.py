#!/usr/bin/env python3
"""robots_preflight.py - ask airbnb.com/robots.txt what this plugin is allowed to fetch.

Why this exists
===============
This plugin runs with robots.txt compliance on, which means the answer to "does
accommodation search work today" is decided by a file on Airbnb's servers that
they can change any morning. Rather than record that answer in a README and let
it rot, this script goes and reads the file.

Run it before a demo. Run it when a search starts failing. It fetches only
`/robots.txt`, which is by definition fetchable, and makes no other request.

    python3 scripts/robots_preflight.py
    python3 scripts/robots_preflight.py --robots-file /tmp/airbnb-robots.txt

Exit 0 when both plugin paths are allowed, 1 when either is disallowed, 2 when
robots.txt could not be fetched.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request

ROBOTS_URL = "https://www.airbnb.com/robots.txt"

# The exact User-Agent the upstream MCP server sends. Robots groups are matched
# against this, so a different string can get a different answer.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Representative paths for the two tools this plugin exposes.
PLUGIN_PATHS = [
    ("airbnb_search", "/s/Lisbon--Portugal/homes?checkin=2026-09-09&adults=2"),
    ("airbnb_listing_details", "/rooms/46175267?check_in=2026-09-09&adults=2"),
]


def parse_groups(robots_txt: str) -> dict[str, list[tuple[str, str]]]:
    """user-agent token -> [(directive, pattern)] in file order.

    A blank line ends a group, so consecutive `User-agent:` lines share one set
    of rules, which is how Airbnb's file is written.
    """
    groups: dict[str, list[tuple[str, str]]] = {}
    current: list[str] = []
    starting_group = False
    for raw in robots_txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            current = []
            starting_group = False
            continue
        if ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if not starting_group:
                current = []
            agent = value.lower()
            current.append(agent)
            groups.setdefault(agent, [])
            starting_group = True
        elif field in ("allow", "disallow") and current:
            starting_group = False
            for agent in current:
                groups[agent].append((field, value))
    return groups


def select_group(groups: dict[str, list[tuple[str, str]]], user_agent: str) -> str:
    """The most specific group whose token appears in the User-Agent, else '*'."""
    ua = user_agent.lower()
    best = ""
    for agent in groups:
        if agent == "*":
            continue
        if agent in ua and len(agent) > len(best):
            best = agent
    return best or "*"


def pattern_to_regex(pattern: str) -> re.Pattern:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    parts = [re.escape(chunk) for chunk in body.split("*")]
    return re.compile("^" + ".*".join(parts) + ("$" if anchored else ""))


def decide(rules: list[tuple[str, str]], path: str) -> tuple[bool, str | None]:
    """Longest matching rule wins; a tie goes to allow. Returns (allowed, rule)."""
    winner: tuple[int, str, str] | None = None
    for directive, pattern in rules:
        if pattern == "":
            # `Disallow:` with an empty value means "nothing is disallowed".
            continue
        if not pattern_to_regex(pattern).match(path):
            continue
        weight = len(pattern)
        if winner is None or weight > winner[0] or (
            weight == winner[0] and directive == "allow"
        ):
            winner = (weight, directive, pattern)
    if winner is None:
        return True, None
    return winner[1] == "allow", f"{winner[1].title()}: {winner[2]}"


def fetch_robots() -> str:
    request = urllib.request.Request(ROBOTS_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robots-file", help="read robots.txt from a file instead of the network")
    args = parser.parse_args()

    if args.robots_file:
        robots_txt = open(args.robots_file, encoding="utf-8").read()
        source = args.robots_file
    else:
        try:
            robots_txt = fetch_robots()
        except (urllib.error.URLError, OSError) as exc:
            print(f"Could not fetch {ROBOTS_URL}: {exc}", file=sys.stderr)
            return 2
        source = ROBOTS_URL

    groups = parse_groups(robots_txt)
    group = select_group(groups, USER_AGENT)
    rules = groups.get(group, [])

    print(f"robots.txt source: {source}")
    print(f"User-Agent sent by the server: {USER_AGENT}")
    print(f"Matching group: User-agent: {group}  ({len(rules)} rules)\n")

    blocked = False
    for tool, path in PLUGIN_PATHS:
        allowed, rule = decide(rules, path)
        verdict = "ALLOWED" if allowed else "DISALLOWED"
        print(f"{verdict:<11} {tool}")
        print(f"            {path}")
        print(f"            matched: {rule or 'no rule, allowed by default'}\n")
        blocked = blocked or not allowed

    if blocked:
        print("At least one path is disallowed. This plugin ships with robots")
        print("compliance on, so those requests will be refused before they are")
        print("made. That is the intended behaviour, not a bug to route around.")
        return 1

    print("Both paths are allowed by robots.txt as of this run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
