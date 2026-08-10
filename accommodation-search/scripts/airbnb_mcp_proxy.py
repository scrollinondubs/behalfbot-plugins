#!/usr/bin/env python3
"""airbnb_mcp_proxy.py - stdio MCP proxy in front of the pinned openbnb Airbnb server.

Why this exists
===============
The upstream server is a scraper. When Airbnb changes its markup the parse can
still succeed against a page that no longer contains listings, and the result is
an empty `searchResults` array with `isError: false`. To a client that is
indistinguishable from "there is genuinely nothing available on those dates",
which is the one answer a travel assistant must never give by accident.

So every `tools/call` result for the two Airbnb tools passes through here on its
way back to the client. An empty or missing result set is rewritten into a
result that says SUSPICIOUS, in the payload and in a leading text block, before
any model ever reads it. This is the mechanical version of the rule - a line in
a skill file is a request, this is a guarantee.

Everything else is forwarded byte-for-byte. The proxy fails open: any message it
cannot parse, any tool it does not know, any shape it does not recognise is
passed through untouched. A bug in the annotation must never be able to break
the transport.

Usage
=====
    python3 scripts/airbnb_mcp_proxy.py [extra args passed to the child server]

Speaks newline-delimited JSON-RPC on stdin/stdout, the MCP stdio transport.
The child's stderr is forwarded to this process's stderr.

Deliberately NOT passed to the child: `--ignore-robots-txt`. Robots compliance
stays on. Turning it off is a decision for the install's owner, not a default
buried in a wrapper.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_ENTRY = (
    PLUGIN_ROOT / "node_modules" / "@openbnb" / "mcp-server-airbnb" / "dist" / "index.js"
)

# tool name -> the key in the upstream JSON payload that holds the result set.
# An empty or absent value under that key is the silent-rot signal.
RESULT_KEY_BY_TOOL = {
    "airbnb_search": "searchResults",
    "airbnb_listing_details": "details",
}

WARNING_MARKER = "_behalfbot_warning"

WARNING_HEADLINE = (
    "SUSPICIOUS EMPTY RESULT - do not report this to the user as "
    "'nothing available'."
)

WARNING_BODY = (
    "This plugin reads airbnb.com by scraping it. When Airbnb changes its page "
    "markup the scrape degrades into an empty result set that looks exactly "
    "like a search that genuinely matched nothing. The two cases cannot be told "
    "apart from this response alone."
)

TELL_THE_USER = (
    "Tell the user what actually happened: the request came back empty and it "
    "could not be confirmed whether that is real. Do not present it as a "
    "finding about availability."
)

WARNING_NEXT_STEPS_BY_TOOL = {
    "airbnb_search": [
        "Re-run the same search with the filters relaxed (drop the price "
        "ceiling, widen the dates, drop the property type). If a broad search "
        "is also empty, the scraper is the more likely explanation than the "
        "market.",
        "Open the searchUrl from this response in a browser and look at it. "
        "That is the ground truth and it takes ten seconds.",
        TELL_THE_USER,
    ],
    "airbnb_listing_details": [
        "Open the listingUrl from this response in a browser. If the listing "
        "is there and this response is empty, the scrape broke.",
        "Try a different listing id. Every listing coming back empty points at "
        "the scraper; one listing coming back empty may just be delisted.",
        TELL_THE_USER,
    ],
}


def child_command(extra_args: list[str] | None = None) -> list[str]:
    """Command that runs the pinned upstream server from node_modules.

    Resolved relative to this file rather than from PATH or an env var. The
    version that runs is the one `npm ci` installed from the committed
    lockfile, and nothing else.
    """
    return ["node", str(UPSTREAM_ENTRY), *(extra_args or [])]


def build_warning(tool_name: str, result_key: str, observed: object) -> dict:
    if observed is None:
        reason = f"the upstream response has no '{result_key}' key at all"
    elif not isinstance(observed, list):
        reason = f"'{result_key}' is a {type(observed).__name__}, not a list"
    else:
        reason = f"'{result_key}' is an empty list"
    return {
        "status": "SUSPICIOUS_EMPTY_RESULT",
        "headline": WARNING_HEADLINE,
        "tool": tool_name,
        "what_was_observed": reason,
        "why_it_is_suspicious": WARNING_BODY,
        "what_to_do": WARNING_NEXT_STEPS_BY_TOOL[tool_name],
    }


def annotate_tool_result(result: dict, tool_name: str) -> dict:
    """Return the tools/call result, annotated if its result set looks rotted.

    Pure and total: returns the input unchanged for anything it does not
    recognise, and never raises on malformed input.
    """
    result_key = RESULT_KEY_BY_TOOL.get(tool_name)
    if result_key is None or not isinstance(result, dict):
        return result
    if result.get("isError"):
        # Upstream already said something went wrong, loudly. Nothing to add.
        return result

    content = result.get("content")
    if not isinstance(content, list) or not content:
        return result
    first = content[0]
    if not isinstance(first, dict) or first.get("type") != "text":
        return result
    text = first.get("text")
    if not isinstance(text, str):
        return result

    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        return result
    if not isinstance(payload, dict):
        return result
    if payload.get("error") is not None or WARNING_MARKER in payload:
        return result

    observed = payload.get(result_key)
    if isinstance(observed, list) and observed:
        return result

    warning = build_warning(tool_name, result_key, observed)
    payload[WARNING_MARKER] = warning

    annotated = dict(result)
    annotated["content"] = [
        {
            "type": "text",
            "text": (
                f"{warning['headline']}\n\n"
                f"Observed: {warning['what_was_observed']}.\n\n"
                f"{WARNING_BODY}\n\n"
                + "\n".join(f"- {step}" for step in warning["what_to_do"])
            ),
        },
        {**first, "text": json.dumps(payload, indent=2)},
        *content[1:],
    ]
    return annotated


def annotate_response(message: dict, tool_by_id: dict) -> dict:
    """Annotate an inbound JSON-RPC response if it answers a known tools/call."""
    if not isinstance(message, dict):
        return message
    msg_id = message.get("id")
    if msg_id is None:
        return message
    tool_name = tool_by_id.pop(_id_key(msg_id), None)
    if tool_name is None:
        return message
    result = message.get("result")
    if not isinstance(result, dict):
        return message
    annotated = dict(message)
    annotated["result"] = annotate_tool_result(result, tool_name)
    return annotated


def record_request(message: dict, tool_by_id: dict) -> None:
    """Remember which tool an outbound tools/call asked for, keyed by its id."""
    if not isinstance(message, dict) or message.get("method") != "tools/call":
        return
    msg_id = message.get("id")
    params = message.get("params")
    if msg_id is None or not isinstance(params, dict):
        return
    name = params.get("name")
    if isinstance(name, str):
        tool_by_id[_id_key(msg_id)] = name


def _id_key(msg_id: object) -> str:
    """JSON-RPC ids may be int or string. Key on both shapes the same way."""
    return f"{type(msg_id).__name__}:{msg_id}"


def _pump_client_to_child(child_stdin, tool_by_id: dict) -> None:
    for raw in sys.stdin.buffer:
        try:
            message = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            message = None
        if isinstance(message, dict):
            record_request(message, tool_by_id)
        try:
            child_stdin.write(raw)
            child_stdin.flush()
        except (BrokenPipeError, ValueError):
            return
    try:
        child_stdin.close()
    except (BrokenPipeError, ValueError):
        pass


def main(argv: list[str]) -> int:
    if not UPSTREAM_ENTRY.exists():
        sys.stderr.write(
            "[accommodation-search] ERROR: the pinned Airbnb MCP server is not "
            f"installed at {UPSTREAM_ENTRY}.\n"
            "[accommodation-search]        Run this plugin's setup.sh, which "
            "installs it with `npm ci` from the committed lockfile.\n"
        )
        return 1

    env = dict(os.environ)
    # DISABLE_GEOCODING stays unset on purpose. With it set, Airbnb's own
    # geocoder resolves the location string and it mishandles non-US queries -
    # "Copenhagen, Denmark" lands in Wisconsin. The cost is that the location
    # string goes to Photon and possibly Nominatim on every search, which is
    # declared in the manifest and documented in the README.
    env.pop("DISABLE_GEOCODING", None)

    child = subprocess.Popen(
        child_command(argv[1:]),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        env=env,
    )

    tool_by_id: dict = {}
    writer = threading.Thread(
        target=_pump_client_to_child, args=(child.stdin, tool_by_id), daemon=True
    )
    writer.start()

    out = sys.stdout.buffer
    for raw in child.stdout:
        try:
            message = json.loads(raw.decode("utf-8"))
            if isinstance(message, dict):
                message = annotate_response(message, tool_by_id)
                raw = (json.dumps(message) + "\n").encode("utf-8")
        except (ValueError, UnicodeDecodeError, TypeError):
            pass
        out.write(raw)
        out.flush()

    return child.wait()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
