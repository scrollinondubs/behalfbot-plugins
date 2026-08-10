#!/usr/bin/env python3
"""Shared test scaffolding. Not a suite - the runner discovers test_*.py only.

Everything here is standard library. No network, no credentials, no pip
install. That is not a preference: the repo's CI runner has no install step and
a plugin suite that needs one will quietly stop running.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = PLUGIN_ROOT / "tests" / "fixtures"
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))


def fixture(*parts: str) -> dict:
    with (FIXTURES.joinpath(*parts)).open(encoding="utf-8") as handle:
        return json.load(handle)


class FakeTransport:
    """Replays queued responses in order and records what was asked for.

    Each queued entry is (http_status, body_dict). A request beyond the end of
    the queue is a test bug and raises rather than returning something
    plausible.
    """

    def __init__(self, *responses) -> None:
        self.queue = list(responses)
        self.requests: list[dict] = []

    def request(self, method: str, url: str, headers: dict, body: bytes | None):
        self.requests.append({"method": method, "url": url, "headers": headers, "body": body})
        if not self.queue:
            raise AssertionError(f"unexpected extra request to {url}")
        status, payload = self.queue.pop(0)
        return status, json.dumps(payload).encode("utf-8")


TOKEN_OK = (
    200,
    {"access_token": "test-token-value", "expires_in": 1799, "token_type": "Bearer"},
)


def temp_budget(monthly_budget: int = 2000):
    """A CallBudget writing into a throwaway directory."""
    from call_budget import CallBudget

    directory = tempfile.mkdtemp(prefix="accommodation-search-test-")
    return CallBudget(pathlib.Path(directory) / "call-ledger.json", monthly_budget=monthly_budget)


def make_client(*responses, budget=None, environment: str = "test"):
    from amadeus_client import AmadeusClient

    return AmadeusClient(
        client_id="test-client-id",
        client_secret="test-client-secret-value",
        environment=environment,
        transport=FakeTransport(*responses),
        budget=budget or temp_budget(),
        sleeper=lambda _seconds: None,
    )


def make_supplier(*responses, budget=None):
    from amadeus_supplier import AmadeusSupplier

    return AmadeusSupplier(make_client(*responses, budget=budget))
