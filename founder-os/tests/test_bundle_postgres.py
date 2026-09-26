#!/usr/bin/env python3
"""test_bundle_postgres.py - founder bundle round trip on Postgres, and across engines.

Needs a Postgres, so it SKIPS (exit 0, and says so) unless FOUNDER_OS_TEST_PG_DSN
is set and psycopg imports. CI has neither. Run it only against a throwaway
container started with --rm, and stop the container afterwards:

    docker run -d --rm --name fos-pg -p 127.0.0.1:55432:5432 \
        -e POSTGRES_PASSWORD=<pick-one> postgres:17
    FOUNDER_OS_TEST_PG_DSN=postgresql://postgres:<pick-one>@127.0.0.1:55432/postgres \
        python3 founder-os/tests/test_bundle_postgres.py
    docker stop fos-pg

Every ledger gets its own founder_os_test_<random> schema. The suite never
removes anything: stopping the --rm container is the cleanup. Never point it at
a database you want to keep. The cross-engine cases export from SQLite and
import into Postgres (and back), and require the same bytes out as went in.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid

from bundle_roundtrip import BundleRoundTrip, populate, run, without_export_time

from founder_bundle import export_bundle, import_bundle
from founder_bundle.bundle import load_files
from founder_ledger import SqliteLedger

DSN = os.environ.get("FOUNDER_OS_TEST_PG_DSN")


class PostgresBundleTest(BundleRoundTrip, unittest.TestCase):
    def make_ledger(self):
        from founder_ledger import PostgresLedger

        ledger = PostgresLedger(DSN, schema="founder_os_test_" + uuid.uuid4().hex[:12])
        ledger.run_migrations()
        return ledger

    def sqlite(self):
        ledger = SqliteLedger(":memory:")
        ledger.run_migrations()
        self.ledgers.append(ledger)
        return ledger

    def cross(self, src, fid, dst):
        first = self.tmp / "first"
        export_bundle(src, fid, first, files_dir=self.files_src)
        import_bundle(dst, first, files_dir=self.tmp / "fx")
        second = self.tmp / "second"
        export_bundle(dst, fid, second, files_dir=self.tmp / "fx")
        self.assertEqual(without_export_time(load_files(first)), without_export_time(load_files(second)))

    def test_postgres_to_sqlite_is_identical(self):
        self.cross(self.src, self.fid, self.sqlite())

    def test_sqlite_to_postgres_is_identical(self):
        lite = self.sqlite()
        self.cross(lite, populate(lite, self.files_src), self.fresh())


if __name__ == "__main__":
    if not DSN:
        print("SKIP: FOUNDER_OS_TEST_PG_DSN not set - Postgres bundle round trip not run")
        raise SystemExit(0)
    try:
        import psycopg  # noqa: F401
    except ImportError:
        print("SKIP: psycopg not installed - Postgres bundle round trip not run")
        raise SystemExit(0)
    sys.exit(run(PostgresBundleTest))
