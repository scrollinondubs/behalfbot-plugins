#!/usr/bin/env python3
"""test_bundle_sqlite.py - founder bundle round trip on SQLite.

Stdlib only, so it runs in CI. Exports a founder with a row in every table,
imports it into a fresh database, exports again and compares the two bundles
byte for byte, excluding only the manifest's exported_at. Also covers
idempotency, conflicts, id remapping, version and checksum refusal, and the
progress webhook against a loopback server.

Run:
    python3 founder-os/tests/test_bundle_sqlite.py
"""
from __future__ import annotations

import unittest

from bundle_roundtrip import BundleRoundTrip, ProgressWebhookTest, run

from founder_ledger import SqliteLedger


class SqliteBundleTest(BundleRoundTrip, unittest.TestCase):
    def make_ledger(self):
        ledger = SqliteLedger(":memory:")
        ledger.run_migrations()
        return ledger


if __name__ == "__main__":
    raise SystemExit(run(SqliteBundleTest, ProgressWebhookTest))
