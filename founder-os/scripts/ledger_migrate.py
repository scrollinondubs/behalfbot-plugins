#!/usr/bin/env python3
"""ledger_migrate.py - apply FounderOS ledger migrations to the configured backend.

Reads the same environment as founder_ledger.open_ledger():

    FOUNDER_OS_LEDGER_BACKEND   postgres (default) | sqlite
    BEHALFBOT_PG_DSN / CHASSIS_PG_DSN
    FOUNDER_OS_PG_SCHEMA        default founder_os
    FOUNDER_OS_SQLITE_PATH

Safe to re-run: applied versions are recorded in ledger_migrations and skipped.
On Postgres it creates the ledger schema if missing and touches nothing outside it.

Usage:
    python3 ledger_migrate.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from founder_ledger import open_ledger  # noqa: E402


def main() -> int:
    with open_ledger() as ledger:
        applied = ledger.run_migrations()
    print(f"applied: {', '.join(applied)}" if applied else "ledger schema already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
