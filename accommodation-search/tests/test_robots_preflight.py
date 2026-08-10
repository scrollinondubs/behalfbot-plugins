#!/usr/bin/env python3
"""Tests for robots_preflight.py.

Stdlib only, no network. Runs against a trimmed fixture copy of Airbnb's
robots.txt, and the expected verdicts were cross-checked against the
`robots-parser` library the upstream MCP server itself uses.

Run:  python3 accommodation-search/tests/test_robots_preflight.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "robots-sample.txt"

_spec = importlib.util.spec_from_file_location(
    "robots_preflight", PLUGIN_ROOT / "scripts" / "robots_preflight.py"
)
preflight = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preflight)

ROBOTS = FIXTURE.read_text(encoding="utf-8")


def verdict(path: str) -> bool:
    groups = preflight.parse_groups(ROBOTS)
    group = preflight.select_group(groups, preflight.USER_AGENT)
    allowed, _ = preflight.decide(groups[group], path)
    return allowed


class TheRightGroupIsSelected(unittest.TestCase):
    def test_a_browser_user_agent_falls_through_to_the_wildcard_group(self):
        groups = preflight.parse_groups(ROBOTS)
        self.assertEqual(preflight.select_group(groups, preflight.USER_AGENT), "*")

    def test_a_named_crawler_gets_its_own_group(self):
        groups = preflight.parse_groups(ROBOTS)
        self.assertEqual(
            preflight.select_group(groups, "Mozilla/5.0 (compatible; Googlebot/2.1)"),
            "googlebot",
        )

    def test_a_blank_line_ends_a_group(self):
        groups = preflight.parse_groups(ROBOTS)
        self.assertNotIn(("disallow", "/things-to-do/places"), groups["googlebot"])


class TheTwoPluginPathsGetTheKnownAnswer(unittest.TestCase):
    def test_search_is_disallowed(self):
        # Disallow: /s/*/* covers every Airbnb search URL, which always has the
        # shape /s/<location>/homes. This is why the search tool cannot run with
        # robots compliance on.
        self.assertFalse(verdict("/s/Lisbon--Portugal/homes?checkin=2026-09-09"))

    def test_listing_details_are_allowed(self):
        self.assertTrue(verdict("/rooms/46175267?check_in=2026-09-09&adults=2"))

    def test_the_disallowed_listing_subpages_are_still_disallowed(self):
        self.assertFalse(verdict("/rooms/46175267/amenities"))
        self.assertFalse(verdict("/rooms/46175267/house-rules"))


class PatternMatchingFollowsTheStandard(unittest.TestCase):
    def test_a_wildcard_matches_any_run_of_characters(self):
        self.assertTrue(preflight.pattern_to_regex("/s/*/*").match("/s/a/b"))
        self.assertFalse(preflight.pattern_to_regex("/s/*/*").match("/s/a"))

    def test_a_dollar_anchors_the_end(self):
        self.assertTrue(preflight.pattern_to_regex("/x$").match("/x"))
        self.assertFalse(preflight.pattern_to_regex("/x$").match("/xy"))

    def test_the_longest_matching_rule_wins(self):
        rules = [("disallow", "/a"), ("allow", "/a/b")]
        allowed, rule = preflight.decide(rules, "/a/b/c")
        self.assertTrue(allowed)
        self.assertEqual(rule, "Allow: /a/b")

    def test_a_tie_goes_to_allow(self):
        rules = [("disallow", "/a"), ("allow", "/a")]
        allowed, _ = preflight.decide(rules, "/a")
        self.assertTrue(allowed)

    def test_an_empty_disallow_blocks_nothing(self):
        allowed, rule = preflight.decide([("disallow", "")], "/anything")
        self.assertTrue(allowed)
        self.assertIsNone(rule)

    def test_a_path_with_no_matching_rule_is_allowed(self):
        allowed, rule = preflight.decide([("disallow", "/nope")], "/rooms/1")
        self.assertTrue(allowed)
        self.assertIsNone(rule)


if __name__ == "__main__":
    unittest.main(verbosity=2, argv=[sys.argv[0]])
