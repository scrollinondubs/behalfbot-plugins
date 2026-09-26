#!/usr/bin/env python3
"""test_ledger_sqlite.py - ledger conformance suite on SQLite.

Stdlib only, so it runs in CI. Each case gets a fresh in-memory database with
every migration applied. SQLite is also the reference for libSQL/Turso.

Run:
    python3 founder-os/tests/test_ledger_sqlite.py
"""
from __future__ import annotations

import unittest

from ledger_conformance import LedgerConformance, run

from founder_ledger import SqliteLedger


class SqliteLedgerTest(LedgerConformance, unittest.TestCase):
    def make_ledger(self):
        ledger = SqliteLedger(":memory:")
        ledger.run_migrations()
        return ledger


if __name__ == "__main__":
    raise SystemExit(run(SqliteLedgerTest))
