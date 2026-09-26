"""Migration runner shared by every adapter.

Applies schema/migrations/NNN_*.sql in order, each in its own transaction, and
records the version in ledger_migrations. The migration files hold no
transaction statements; this runner owns the transaction.

Statements are split on `;` after stripping `--` comments, which is why the
migration files must not put `;` or `--` inside string literals.
"""
from __future__ import annotations

import pathlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sql import SqlLedger

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "schema" / "migrations"
MIGRATION_NAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


def migration_files(directory: pathlib.Path = MIGRATIONS_DIR) -> list[tuple[str, pathlib.Path]]:
    files = []
    for path in sorted(directory.glob("*.sql")):
        m = MIGRATION_NAME.match(path.name)
        if not m:
            raise ValueError(f"migration file name {path.name!r} is not NNN_snake_case.sql")
        files.append((m.group(1), path))
    return files


def split_statements(script: str) -> list[str]:
    stripped = "\n".join(line.split("--", 1)[0] for line in script.splitlines())
    return [s.strip() for s in stripped.split(";") if s.strip()]


def apply_migrations(ledger: "SqlLedger", directory: pathlib.Path = MIGRATIONS_DIR) -> list[str]:
    ledger._execute(
        "CREATE TABLE IF NOT EXISTS ledger_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    done = {r["version"] for r in ledger._fetch("SELECT version FROM ledger_migrations")}
    applied = []
    for version, path in migration_files(directory):
        if version in done:
            continue
        from .sql import now
        with ledger._tx():
            for statement in split_statements(path.read_text(encoding="utf-8")):
                ledger._execute(statement)
            ledger._execute("INSERT INTO ledger_migrations (version, applied_at) VALUES (?, ?)", (version, now()))
        applied.append(version)
    return applied
