"""FounderOS ledger: the storage interface stage skills call.

    import sys; sys.path.insert(0, os.environ["FOUNDER_OS_DIR"])
    from founder_ledger import open_ledger

    with open_ledger() as ledger:
        founder = ledger.get_founder(founder_id)

open_ledger() reads the backend from the environment the manifest declares:

    FOUNDER_OS_LEDGER_BACKEND   postgres (default) | sqlite
    BEHALFBOT_PG_DSN / CHASSIS_PG_DSN   Postgres DSN, same names the chassis uses
    FOUNDER_OS_PG_SCHEMA        Postgres schema for the ledger (default founder_os)
    FOUNDER_OS_SQLITE_PATH      SQLite file when the backend is sqlite
"""
from __future__ import annotations

import os

from .interface import Ledger, LedgerError, NotFound
from .sqlite_adapter import SqliteLedger

__all__ = ["Ledger", "LedgerError", "NotFound", "SqliteLedger", "PostgresLedger", "open_ledger"]


def __getattr__(name: str):
    if name == "PostgresLedger":
        from .postgres_adapter import PostgresLedger
        return PostgresLedger
    raise AttributeError(name)


def open_ledger(*, migrate: bool = False) -> Ledger:
    backend = os.environ.get("FOUNDER_OS_LEDGER_BACKEND", "postgres").strip().lower()
    if backend == "sqlite":
        path = os.environ.get("FOUNDER_OS_SQLITE_PATH")
        if not path:
            raise RuntimeError("FOUNDER_OS_LEDGER_BACKEND=sqlite needs FOUNDER_OS_SQLITE_PATH")
        ledger = SqliteLedger(path)
    elif backend == "postgres":
        dsn = os.environ.get("BEHALFBOT_PG_DSN") or os.environ.get("CHASSIS_PG_DSN")
        if not dsn:
            raise RuntimeError("the postgres ledger backend needs BEHALFBOT_PG_DSN or CHASSIS_PG_DSN")
        from .postgres_adapter import PostgresLedger
        ledger = PostgresLedger(dsn, os.environ.get("FOUNDER_OS_PG_SCHEMA", "founder_os"))
    else:
        raise RuntimeError(f"unknown FOUNDER_OS_LEDGER_BACKEND {backend!r} (postgres or sqlite)")
    if migrate:
        ledger.run_migrations()
    return ledger
