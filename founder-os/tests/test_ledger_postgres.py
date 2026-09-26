#!/usr/bin/env python3
"""test_ledger_postgres.py - ledger conformance suite on Postgres.

Needs a Postgres to talk to, so it SKIPS (exit 0, and says so) unless
FOUNDER_OS_TEST_PG_DSN is set and psycopg imports. CI has neither, by the
plugin-tests contract. Run it locally against a throwaway container:

    docker run -d --rm --name fos-pg -p 127.0.0.1:55432:5432 \
        -e POSTGRES_PASSWORD=<pick-one> postgres:17
    FOUNDER_OS_TEST_PG_DSN=postgresql://postgres:<pick-one>@127.0.0.1:55432/postgres \
        python3 founder-os/tests/test_ledger_postgres.py

Every case creates its own schema named founder_os_test_<random> and removes
only that schema afterwards. Point it at a throwaway database, never at a
chassis database with real data in it.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid

from ledger_conformance import LedgerConformance, run

DSN = os.environ.get("FOUNDER_OS_TEST_PG_DSN")
TEST_SCHEMA_PREFIX = "founder_os_test_"


class PostgresLedgerTest(LedgerConformance, unittest.TestCase):
    def make_ledger(self):
        from founder_ledger import PostgresLedger

        self.schema = TEST_SCHEMA_PREFIX + uuid.uuid4().hex[:12]
        ledger = PostgresLedger(DSN, schema=self.schema)
        ledger.run_migrations()
        return ledger

    def tearDown(self):
        super().tearDown()
        import psycopg

        if not self.schema.startswith(TEST_SCHEMA_PREFIX):
            raise AssertionError(f"refusing to remove non-test schema {self.schema!r}")
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute(f"DROP SCHEMA {self.schema} CASCADE")


if __name__ == "__main__":
    if not DSN:
        print("SKIP: FOUNDER_OS_TEST_PG_DSN not set - Postgres conformance not run")
        raise SystemExit(0)
    try:
        import psycopg  # noqa: F401
    except ImportError:
        print("SKIP: psycopg not installed - Postgres conformance not run")
        raise SystemExit(0)
    sys.exit(run(PostgresLedgerTest))
