"""Postgres adapter for self-hosted Behalf.bot.

The ledger lives in its own Postgres schema (default `founder_os`) and the
connection's search_path points at it. That keeps generic table names like
`artifacts` and `labels` from colliding with anything else in the chassis
database, while the migrations stay unqualified and run unchanged on SQLite.

Needs psycopg 3, which the chassis image already ships. It is imported lazily
so the rest of the package, and the SQLite tests, work without it.
"""
from __future__ import annotations

import re

from .sql import SqlLedger

SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class PostgresLedger(SqlLedger):
    def __init__(self, dsn: str, schema: str = "founder_os") -> None:
        super().__init__()
        if not SCHEMA_NAME.match(schema):
            raise ValueError(f"schema name {schema!r} must match {SCHEMA_NAME.pattern}")
        import psycopg
        from psycopg.rows import dict_row

        self.schema = schema
        # autocommit: a bare read never leaves a transaction open. Writes go
        # through _tx, which opens an explicit one.
        self._conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)
        self._conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        self._conn.execute(f"SET search_path TO {schema}")

    @staticmethod
    def _pg(sql: str) -> str:
        return sql.replace("?", "%s")

    def _execute(self, sql, params=()):
        self._conn.execute(self._pg(sql), params or None)

    def _fetch(self, sql, params=()):
        return [dict(r) for r in self._conn.execute(self._pg(sql), params or None).fetchall()]

    def _begin(self):
        self._conn.execute("BEGIN")

    def _commit(self):
        self._conn.execute("COMMIT")

    def _rollback(self):
        self._conn.execute("ROLLBACK")

    def close(self):
        self._conn.close()
