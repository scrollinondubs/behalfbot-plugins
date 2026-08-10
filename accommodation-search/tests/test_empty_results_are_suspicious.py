#!/usr/bin/env python3
"""Tests for the empty-result guard in airbnb_mcp_proxy.py.

Stdlib only, no network, no node. The upstream MCP call is mocked with canned
payloads captured from the shapes the openbnb server actually emits, so CI does
not depend on Airbnb being up - which is the whole point, since the thing under
test is what happens when Airbnb goes sideways.

Run:  python3 accommodation-search/tests/test_empty_results_are_suspicious.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import unittest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "airbnb_mcp_proxy", PLUGIN_ROOT / "scripts" / "airbnb_mcp_proxy.py"
)
proxy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(proxy)


def tool_result(payload: dict, is_error: bool = False) -> dict:
    """The shape the upstream server returns: one text block of JSON."""
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
        "isError": is_error,
    }


def inner_payload(result: dict) -> dict:
    """Pull the JSON payload back out of whichever text block now holds it."""
    for block in result["content"]:
        try:
            parsed = json.loads(block["text"])
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    raise AssertionError("no JSON payload found in the result content")


ONE_LISTING = {
    "id": "1234567890",
    "url": "https://www.airbnb.com/rooms/1234567890",
    "demandStayListing": {"description": "Bright flat in Alfama"},
}

POPULATED_SEARCH = {
    "searchUrl": "https://www.airbnb.com/s/Lisbon--Portugal/homes",
    "searchResults": [ONE_LISTING],
    "paginationInfo": {"nextPageCursor": "abc"},
}

EMPTY_SEARCH = {
    "searchUrl": "https://www.airbnb.com/s/Lisbon--Portugal/homes",
    "searchResults": [],
    "paginationInfo": {},
}

MISSING_KEY_SEARCH = {
    "searchUrl": "https://www.airbnb.com/s/Lisbon--Portugal/homes",
    "paginationInfo": {},
}

UPSTREAM_ERROR = {
    "error": "Failed to parse search results from Airbnb. The page structure may have changed.",
    "searchUrl": "https://www.airbnb.com/s/Lisbon--Portugal/homes",
}


class EmptySearchIsFlagged(unittest.TestCase):
    def test_empty_result_set_is_marked_suspicious(self):
        annotated = proxy.annotate_tool_result(tool_result(EMPTY_SEARCH), "airbnb_search")
        payload = inner_payload(annotated)
        self.assertEqual(
            payload[proxy.WARNING_MARKER]["status"], "SUSPICIOUS_EMPTY_RESULT"
        )

    def test_the_warning_is_visible_without_parsing_json(self):
        # An agent that reads only the first content block still sees it.
        annotated = proxy.annotate_tool_result(tool_result(EMPTY_SEARCH), "airbnb_search")
        self.assertIn("SUSPICIOUS", annotated["content"][0]["text"])

    def test_the_warning_forbids_the_nothing_available_reading(self):
        annotated = proxy.annotate_tool_result(tool_result(EMPTY_SEARCH), "airbnb_search")
        self.assertIn("nothing available", annotated["content"][0]["text"])

    def test_a_missing_result_key_is_flagged_too(self):
        annotated = proxy.annotate_tool_result(
            tool_result(MISSING_KEY_SEARCH), "airbnb_search"
        )
        payload = inner_payload(annotated)
        self.assertEqual(
            payload[proxy.WARNING_MARKER]["status"], "SUSPICIOUS_EMPTY_RESULT"
        )
        self.assertIn("no 'searchResults' key", payload[proxy.WARNING_MARKER]["what_was_observed"])

    def test_the_original_payload_survives_annotation(self):
        annotated = proxy.annotate_tool_result(tool_result(EMPTY_SEARCH), "airbnb_search")
        payload = inner_payload(annotated)
        self.assertEqual(payload["searchUrl"], EMPTY_SEARCH["searchUrl"])

    def test_empty_listing_details_are_flagged(self):
        result = tool_result({"listingUrl": "https://www.airbnb.com/rooms/1", "details": []})
        annotated = proxy.annotate_tool_result(result, "airbnb_listing_details")
        payload = inner_payload(annotated)
        self.assertEqual(
            payload[proxy.WARNING_MARKER]["status"], "SUSPICIOUS_EMPTY_RESULT"
        )

    def test_the_next_steps_match_the_tool_that_was_called(self):
        # Telling someone to relax the search filters after a listing-details
        # call is advice they cannot act on.
        search = proxy.annotate_tool_result(tool_result(EMPTY_SEARCH), "airbnb_search")
        details = proxy.annotate_tool_result(
            tool_result({"listingUrl": "https://www.airbnb.com/rooms/1", "details": []}),
            "airbnb_listing_details",
        )
        self.assertIn("searchUrl", search["content"][0]["text"])
        self.assertIn("listingUrl", details["content"][0]["text"])
        self.assertNotIn("relaxed", details["content"][0]["text"])


class GoodResultsAreLeftAlone(unittest.TestCase):
    def test_a_populated_search_is_returned_untouched(self):
        original = tool_result(POPULATED_SEARCH)
        self.assertEqual(
            proxy.annotate_tool_result(original, "airbnb_search"), original
        )

    def test_an_upstream_error_is_returned_untouched(self):
        original = tool_result(UPSTREAM_ERROR, is_error=True)
        self.assertEqual(
            proxy.annotate_tool_result(original, "airbnb_search"), original
        )

    def test_an_error_payload_without_the_error_flag_is_untouched(self):
        original = tool_result(UPSTREAM_ERROR)
        self.assertEqual(
            proxy.annotate_tool_result(original, "airbnb_search"), original
        )

    def test_an_unknown_tool_is_untouched(self):
        original = tool_result(EMPTY_SEARCH)
        self.assertEqual(
            proxy.annotate_tool_result(original, "some_other_tool"), original
        )

    def test_annotating_twice_does_not_stack_warnings(self):
        once = proxy.annotate_tool_result(tool_result(EMPTY_SEARCH), "airbnb_search")
        twice = proxy.annotate_tool_result(once, "airbnb_search")
        self.assertEqual(once, twice)


class TheProxyFailsOpen(unittest.TestCase):
    def test_non_json_text_is_passed_through(self):
        original = {"content": [{"type": "text", "text": "<html>oh no</html>"}], "isError": False}
        self.assertEqual(
            proxy.annotate_tool_result(original, "airbnb_search"), original
        )

    def test_empty_content_is_passed_through(self):
        original = {"content": [], "isError": False}
        self.assertEqual(
            proxy.annotate_tool_result(original, "airbnb_search"), original
        )

    def test_a_non_text_content_block_is_passed_through(self):
        original = {"content": [{"type": "image", "data": "..."}], "isError": False}
        self.assertEqual(
            proxy.annotate_tool_result(original, "airbnb_search"), original
        )

    def test_a_result_that_is_not_a_dict_is_passed_through(self):
        self.assertEqual(proxy.annotate_tool_result([], "airbnb_search"), [])


class RequestIdsAreTrackedBackToTools(unittest.TestCase):
    def test_a_response_is_matched_to_the_tool_that_was_called(self):
        tool_by_id: dict = {}
        proxy.record_request(
            {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
             "params": {"name": "airbnb_search", "arguments": {"location": "Lisbon, Portugal"}}},
            tool_by_id,
        )
        response = {"jsonrpc": "2.0", "id": 7, "result": tool_result(EMPTY_SEARCH)}
        annotated = proxy.annotate_response(response, tool_by_id)
        self.assertIn("SUSPICIOUS", annotated["result"]["content"][0]["text"])

    def test_string_ids_work_the_same_as_int_ids(self):
        tool_by_id: dict = {}
        proxy.record_request(
            {"jsonrpc": "2.0", "id": "req-7", "method": "tools/call",
             "params": {"name": "airbnb_search", "arguments": {}}},
            tool_by_id,
        )
        response = {"jsonrpc": "2.0", "id": "req-7", "result": tool_result(EMPTY_SEARCH)}
        annotated = proxy.annotate_response(response, tool_by_id)
        self.assertIn("SUSPICIOUS", annotated["result"]["content"][0]["text"])

    def test_an_int_id_does_not_collide_with_the_same_string_id(self):
        tool_by_id: dict = {}
        proxy.record_request(
            {"jsonrpc": "2.0", "id": "7", "method": "tools/call",
             "params": {"name": "airbnb_search", "arguments": {}}},
            tool_by_id,
        )
        response = {"jsonrpc": "2.0", "id": 7, "result": tool_result(EMPTY_SEARCH)}
        self.assertEqual(proxy.annotate_response(response, tool_by_id), response)

    def test_responses_to_other_methods_are_untouched(self):
        tool_by_id: dict = {}
        proxy.record_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, tool_by_id
        )
        response = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        self.assertEqual(proxy.annotate_response(response, tool_by_id), response)

    def test_a_notification_with_no_id_is_untouched(self):
        message = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        self.assertEqual(proxy.annotate_response(message, {}), message)


class TheUpstreamIsPinnedAndRobotsCompliant(unittest.TestCase):
    def test_the_child_runs_the_locally_installed_server_not_npx(self):
        command = proxy.child_command()
        self.assertEqual(command[0], "node")
        self.assertIn("node_modules/@openbnb/mcp-server-airbnb", command[1])
        self.assertNotIn("npx", " ".join(command))

    def test_robots_compliance_is_not_disabled_by_default(self):
        self.assertNotIn("--ignore-robots-txt", " ".join(proxy.child_command()))

    def test_the_manifest_pins_an_exact_upstream_version(self):
        pkg = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))
        pinned = pkg["dependencies"]["@openbnb/mcp-server-airbnb"]
        self.assertRegex(pinned, r"^\d+\.\d+\.\d+$")

    def test_the_lockfile_agrees_with_the_pin(self):
        pkg = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((PLUGIN_ROOT / "package-lock.json").read_text(encoding="utf-8"))
        entry = lock["packages"]["node_modules/@openbnb/mcp-server-airbnb"]
        self.assertEqual(entry["version"], pkg["dependencies"]["@openbnb/mcp-server-airbnb"])
        self.assertTrue(entry["integrity"].startswith("sha512-"))


if __name__ == "__main__":
    unittest.main(verbosity=2, argv=[sys.argv[0]])
