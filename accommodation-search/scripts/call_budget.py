#!/usr/bin/env python3
"""A monthly ledger of supplier calls, and a local ceiling on them.

Why a local ledger when the supplier has its own quota
=====================================================
Because the supplier will not tell you where you are in it. Amadeus publishes
the free monthly quota only inside its own workspace UI, with a reporting lag
of up to twelve minutes, and the API returns nothing about remaining calls on a
successful response. The first signal that the quota is gone is a 429 with code
38195, arriving in the middle of somebody's trip planning.

So this counts locally. The count is an approximation of the supplier's - a
call that fails in transit still spent something, a call the supplier rejected
for a bad parameter may not have - and it is not presented as authoritative.
It exists to answer "roughly how much of the month have we used" without an
extra API call, and to stop a runaway loop before it eats the month.

What is stored
==============
A single JSON file, one object, replaced whole on each write:

    {
      "month": "2026-08",
      "total": 37,
      "by_endpoint": {"hotel-list": 12, "hotel-offers": 12, "token": 13},
      "fixture_calls": 4,
      "updated_at": "2026-08-10T18:22:04Z"
    }

No credentials, no request parameters, no responses. Endpoint labels and
integers. A month that does not match the current UTC month is discarded and
started fresh, so rollover needs no cron and no cleanup.

`fixture_calls` counts the offline demo path separately and never against the
budget, because those calls never left the machine.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from accommodation_errors import LOCAL_BUDGET_EXHAUSTED, AccommodationError

# Sean's working assumption for the Amadeus free tier, carried over from the
# issue. It is NOT a published figure - Amadeus states only that the free
# monthly allowance "varies from one API to another" and shows the number
# nowhere in its documentation. Treated here as a local safety ceiling that a
# human chose, not as knowledge of the supplier's limit.
DEFAULT_MONTHLY_BUDGET = 2000

# Fraction of the budget at which every response starts carrying a warning.
WARN_AT = 0.8


def _utc_month(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m")


class CallBudget:
    """Counts supplier calls for the current UTC month and refuses past a ceiling."""

    def __init__(
        self,
        path: str | os.PathLike,
        monthly_budget: int = DEFAULT_MONTHLY_BUDGET,
        clock=None,
    ) -> None:
        self.path = Path(path)
        self.monthly_budget = int(monthly_budget)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        return self._clock()

    def read(self) -> dict:
        """Current month's ledger. A missing, unreadable or stale file reads as
        a fresh month rather than raising - a broken counter must never be able
        to block a search."""
        blank = {
            "month": _utc_month(self._now()),
            "total": 0,
            "by_endpoint": {},
            "fixture_calls": 0,
            "updated_at": None,
        }
        try:
            with self.path.open(encoding="utf-8") as handle:
                stored = json.load(handle)
        except (OSError, ValueError):
            return blank
        if not isinstance(stored, dict) or stored.get("month") != blank["month"]:
            return blank
        blank.update(
            {
                "total": int(stored.get("total") or 0),
                "by_endpoint": dict(stored.get("by_endpoint") or {}),
                "fixture_calls": int(stored.get("fixture_calls") or 0),
                "updated_at": stored.get("updated_at"),
            }
        )
        return blank

    def check(self) -> None:
        """Raise before spending a call that would cross the local ceiling."""
        ledger = self.read()
        if ledger["total"] < self.monthly_budget:
            return
        raise AccommodationError(
            kind=LOCAL_BUDGET_EXHAUSTED,
            message=(
                f"Local monthly call budget reached: {ledger['total']} of "
                f"{self.monthly_budget} calls counted for {ledger['month']}. "
                f"No request was sent to the supplier. This is this plugin's "
                f"own ceiling, not the supplier's - the supplier has not "
                f"refused anything."
            ),
            what_to_do=[
                f"The ledger is at {self.path}. It resets by itself when the "
                f"UTC month changes; deleting the file resets it now.",
                "Raise the ceiling with ACCOMMODATION_MONTHLY_CALL_BUDGET if "
                "the account's real allowance is higher.",
                "Tell the traveller the search was not run, rather than that "
                "nothing was found.",
            ],
            detail={
                "counted_this_month": ledger["total"],
                "local_budget": self.monthly_budget,
                "month": ledger["month"],
                "ledger_path": str(self.path),
                "is_supplier_quota": False,
            },
        )

    def record(self, endpoint: str, fixture: bool = False) -> dict:
        """Add one call and persist. Returns the ledger after the write.

        A failed write is swallowed on purpose: an unwritable state directory
        degrades the count, and losing the count is a smaller problem than
        losing the search.
        """
        ledger = self.read()
        if fixture:
            ledger["fixture_calls"] += 1
        else:
            ledger["total"] += 1
            ledger["by_endpoint"][endpoint] = int(ledger["by_endpoint"].get(endpoint, 0)) + 1
        ledger["updated_at"] = self._now().strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(ledger, handle, indent=2, sort_keys=True)
            tmp.replace(self.path)
        except OSError:
            pass
        return ledger

    def usage(self) -> dict:
        """The block attached to every successful tool result."""
        ledger = self.read()
        used = ledger["total"]
        block = {
            "month": ledger["month"],
            "supplier_calls_counted": used,
            "local_monthly_budget": self.monthly_budget,
            "counted_by_endpoint": ledger["by_endpoint"],
            "_note": (
                "Counted locally by this plugin. The supplier does not report "
                "remaining quota on a successful response, so this is an "
                "estimate of spend, not the supplier's own figure."
            ),
        }
        if ledger["fixture_calls"]:
            block["fixture_calls_not_counted"] = ledger["fixture_calls"]
        if self.monthly_budget > 0 and used >= self.monthly_budget * WARN_AT:
            block["warning"] = (
                f"{used} of {self.monthly_budget} local monthly calls used. "
                f"Past {int(WARN_AT * 100)}% - searches will start refusing "
                f"locally at the ceiling."
            )
        return block


def budget_from_env(env=None, plugin_dir: str | os.PathLike | None = None) -> CallBudget:
    env = os.environ if env is None else env
    root = Path(plugin_dir or Path(__file__).resolve().parent.parent)
    state_dir = env.get("ACCOMMODATION_STATE_DIR") or str(root / "var")
    try:
        budget = int(env.get("ACCOMMODATION_MONTHLY_CALL_BUDGET") or DEFAULT_MONTHLY_BUDGET)
    except ValueError:
        budget = DEFAULT_MONTHLY_BUDGET
    return CallBudget(Path(state_dir) / "call-ledger.json", monthly_budget=budget)
