"""SQLite adapter. Used by the tests, and the reference for libSQL/Turso.

Stdlib only. libSQL speaks the same SQL, so this file is also what a Python
Turso adapter would copy: swap sqlite3.connect for the libsql client and keep
everything else.
"""
from __future__ import annotations

import pathlib
import sqlite3

from .sql import SqlLedger


class SqliteLedger(SqlLedger):
    def __init__(self, path: str | pathlib.Path = ":memory:") -> None:
        super().__init__()
        target = str(path)
        if target != ":memory:":
            resolved = pathlib.Path(path).expanduser()
            resolved.parent.mkdir(parents=True, exist_ok=True)
            target = str(resolved)
        # isolation_level=None: no implicit transactions. _tx issues BEGIN and
        # COMMIT itself, so a migration's DDL and its version row commit together.
        self._conn = sqlite3.connect(target, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        # Off by default in SQLite. Without it ON DELETE CASCADE and every
        # REFERENCES clause in the schema are silently ignored.
        self._conn.execute("PRAGMA foreign_keys = ON")

    def _execute(self, sql, params=()):
        self._conn.execute(sql, params)

    def _fetch(self, sql, params=()):
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def _begin(self):
        self._conn.execute("BEGIN")

    def _commit(self):
        self._conn.execute("COMMIT")

    def _rollback(self):
        self._conn.execute("ROLLBACK")

    def close(self):
        self._conn.close()
