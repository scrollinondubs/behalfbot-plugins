"""Shared SQL implementation of the ledger interface.

Every query here is written once, in SQLite's `?` placeholder style, and runs
unchanged on SQLite and Postgres. An adapter supplies only the connection:
how to execute, how to fetch rows as dicts, and how to open a transaction.

Two rules keep the SQL portable. No literal `?` or `%` in any statement, since
the Postgres adapter rewrites `?` to `%s` and psycopg treats `%` as a
placeholder. And table names are interpolated only after checking them against
a fixed allow-list, never from caller input directly.
"""
from __future__ import annotations

import abc
import contextlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator

from .interface import (
    AUDIT_TARGETS, AUDITORS, BUNDLE_TABLES, COMMITMENTS, DECIDERS, DECISIONS, EVIDENCE_TABLES,
    LABEL_TARGETS, SEAN_SIGNOFF_FROM_STAGE, STAGES, TABLE_COLUMNS, VERDICTS,
    Ledger, LedgerError, NotFound, Row,
)

JSON_COLUMNS = {
    "founders": ("context",),
    "artifacts": ("meta",),
    "pains": ("tags",),
    "prfaq_versions": ("assumptions",),
    "gate_decisions": ("evidence",),
    "labels": ("model_label", "corrected_label"),
}
BOOL_COLUMNS = {
    "interviews": ("earlyvangelist",),
    "gate_decisions": ("sean_signoff",),
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def new_id() -> str:
    return str(uuid.uuid4())


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _check_stage(stage: Any, what: str = "stage") -> int:
    if not isinstance(stage, int) or isinstance(stage, bool) or stage not in STAGES:
        raise LedgerError(f"{what} must be an integer 0-9, got {stage!r}")
    return stage


def _check_choice(value: Any, choices: tuple[str, ...], what: str) -> str:
    if value not in choices:
        raise LedgerError(f"{what} must be one of {', '.join(choices)}, got {value!r}")
    return value


def _check_text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LedgerError(f"{what} must be a non-empty string")
    return value


class SqlLedger(Ledger):
    """Ledger over any DB-API connection. Subclasses implement the four hooks."""

    def __init__(self) -> None:
        self._tx_depth = 0

    # --- adapter hooks ------------------------------------------------------

    @abc.abstractmethod
    def _execute(self, sql: str, params: tuple = ()) -> None: ...

    @abc.abstractmethod
    def _fetch(self, sql: str, params: tuple = ()) -> list[dict]: ...

    @abc.abstractmethod
    def _begin(self) -> None: ...

    @abc.abstractmethod
    def _commit(self) -> None: ...

    @abc.abstractmethod
    def _rollback(self) -> None: ...

    # --- plumbing -----------------------------------------------------------

    @contextlib.contextmanager
    def _tx(self) -> Iterator[None]:
        """A transaction. Re-entrant: an inner _tx joins the outer one."""
        if self._tx_depth:
            self._tx_depth += 1
            try:
                yield
            finally:
                self._tx_depth -= 1
            return
        self._begin()
        self._tx_depth = 1
        try:
            yield
        except BaseException:
            self._tx_depth = 0
            self._rollback()
            raise
        self._tx_depth = 0
        self._commit()

    def _rows(self, table: str, sql: str, params: tuple = ()) -> list[Row]:
        rows = self._fetch(sql, params)
        for row in rows:
            for col in JSON_COLUMNS.get(table, ()):
                if row.get(col) is not None:
                    row[col] = json.loads(row[col])
            for col in BOOL_COLUMNS.get(table, ()):
                if row.get(col) is not None:
                    row[col] = bool(row[col])
        return rows

    def _one(self, table: str, sql: str, params: tuple = ()) -> Row | None:
        rows = self._rows(table, sql, params)
        return rows[0] if rows else None

    def _insert(self, table: str, values: dict[str, Any]) -> Row:
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        self._execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(values.values()))
        row = self._one(table, f"SELECT * FROM {table} WHERE id = ?", (values["id"],))
        assert row is not None
        return row

    def _require_founder(self, founder_id: str) -> Row:
        founder = self.get_founder(founder_id)
        if founder is None:
            raise NotFound(f"no founder {founder_id!r}")
        return founder

    def _owns(self, table: str, founder_id: str, row_id: str) -> bool:
        if table not in EVIDENCE_TABLES + ("labels",):
            raise LedgerError(f"unknown ledger table {table!r}")
        return bool(self._fetch(
            f"SELECT 1 AS hit FROM {table} WHERE id = ? AND founder_id = ?", (row_id, founder_id)))

    def run_migrations(self) -> list[str]:
        """Apply any migrations not yet recorded. Returns the versions applied."""
        from .migrate import apply_migrations
        return apply_migrations(self)

    # --- founders -----------------------------------------------------------

    def create_founder(self, display_name, *, cohort=None, context=None, founder_id=None):
        _check_text(display_name, "display_name")
        fid = founder_id or new_id()
        ts = now()
        with self._tx():
            self._execute(
                "INSERT INTO founders (founder_id, display_name, cohort, current_stage, context, created_at, updated_at)"
                " VALUES (?, ?, ?, 0, ?, ?, ?)",
                (fid, display_name, cohort, _dump(context or {}), ts, ts),
            )
            self._open_stage(fid, 0, ts)
        return self.get_founder(fid)

    def get_founder(self, founder_id):
        return self._one("founders", "SELECT * FROM founders WHERE founder_id = ?", (founder_id,))

    def update_founder_context(self, founder_id, context):
        if not isinstance(context, dict):
            raise LedgerError("context must be a dict")
        with self._tx():
            self._require_founder(founder_id)
            self._execute("UPDATE founders SET context = ?, updated_at = ? WHERE founder_id = ?",
                          (_dump(context), now(), founder_id))
        return self.get_founder(founder_id)

    def delete_founder(self, founder_id):
        with self._tx():
            self._require_founder(founder_id)
            self._execute("DELETE FROM founders WHERE founder_id = ?", (founder_id,))

    # --- stage progress -----------------------------------------------------

    def _open_stage(self, founder_id: str, stage: int, ts: str) -> None:
        existing = self._fetch(
            "SELECT id FROM stage_progress WHERE founder_id = ? AND stage = ?", (founder_id, stage))
        if existing:
            self._execute(
                "UPDATE stage_progress SET status = 'in_progress', passed_at = NULL, updated_at = ? WHERE id = ?",
                (ts, existing[0]["id"]))
        else:
            self._execute(
                "INSERT INTO stage_progress (id, founder_id, stage, status, started_at, updated_at)"
                " VALUES (?, ?, ?, 'in_progress', ?, ?)",
                (new_id(), founder_id, stage, ts, ts))

    def list_stage_progress(self, founder_id):
        return self._rows("stage_progress",
                          "SELECT * FROM stage_progress WHERE founder_id = ? ORDER BY stage", (founder_id,))

    def mark_gate_pending(self, founder_id, stage):
        _check_stage(stage)
        with self._tx():
            founder = self._require_founder(founder_id)
            if founder["current_stage"] != stage:
                raise LedgerError(f"founder is at stage {founder['current_stage']}, not {stage}")
            self._execute(
                "UPDATE stage_progress SET status = 'gate_pending', updated_at = ? WHERE founder_id = ? AND stage = ?",
                (now(), founder_id, stage))
        return self._one("stage_progress",
                         "SELECT * FROM stage_progress WHERE founder_id = ? AND stage = ?", (founder_id, stage))

    # --- artifacts ----------------------------------------------------------

    def add_artifact(self, founder_id, *, stage, kind, body, title=None, meta=None):
        _check_stage(stage)
        _check_text(kind, "kind")
        _check_text(body, "body")
        with self._tx():
            self._require_founder(founder_id)
            prev = self._fetch(
                "SELECT COALESCE(MAX(version), 0) AS v FROM artifacts WHERE founder_id = ? AND kind = ?",
                (founder_id, kind))
            return self._insert("artifacts", {
                "id": new_id(), "founder_id": founder_id, "stage": stage, "kind": kind,
                "version": int(prev[0]["v"]) + 1, "title": title, "body": body,
                "meta": _dump(meta or {}), "created_at": now(),
            })

    def get_artifact(self, founder_id, artifact_id):
        return self._one("artifacts", "SELECT * FROM artifacts WHERE founder_id = ? AND id = ?",
                         (founder_id, artifact_id))

    def list_artifacts(self, founder_id, *, stage=None, kind=None):
        sql, params = "SELECT * FROM artifacts WHERE founder_id = ?", [founder_id]
        if stage is not None:
            sql += " AND stage = ?"
            params.append(_check_stage(stage))
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        return self._rows("artifacts", sql + " ORDER BY created_at, kind, version", tuple(params))

    # --- pains --------------------------------------------------------------

    def add_pain(self, founder_id, *, quote, source_url=None, watering_hole=None,
                 segment=None, job=None, tags=None):
        _check_text(quote, "quote")
        with self._tx():
            self._require_founder(founder_id)
            return self._insert("pains", {
                "id": new_id(), "founder_id": founder_id, "quote": quote, "source_url": source_url,
                "watering_hole": watering_hole, "segment": segment, "job": job,
                "tags": _dump(list(tags or [])), "created_at": now(),
            })

    def list_pains(self, founder_id, *, job=None):
        if job is None:
            return self._rows("pains", "SELECT * FROM pains WHERE founder_id = ? ORDER BY created_at", (founder_id,))
        return self._rows("pains", "SELECT * FROM pains WHERE founder_id = ? AND job = ? ORDER BY created_at",
                          (founder_id, job))

    # --- interviews ---------------------------------------------------------

    def add_interview(self, founder_id, *, interviewee, notes, conducted_on=None,
                      segment=None, commitment="none", earlyvangelist=False):
        _check_text(interviewee, "interviewee")
        _check_text(notes, "notes")
        _check_choice(commitment, COMMITMENTS, "commitment")
        with self._tx():
            self._require_founder(founder_id)
            return self._insert("interviews", {
                "id": new_id(), "founder_id": founder_id, "interviewee": interviewee,
                "segment": segment, "conducted_on": conducted_on, "notes": notes,
                "commitment": commitment, "earlyvangelist": 1 if earlyvangelist else 0,
                "created_at": now(),
            })

    def list_interviews(self, founder_id):
        return self._rows("interviews", "SELECT * FROM interviews WHERE founder_id = ? ORDER BY created_at",
                          (founder_id,))

    # --- audits -------------------------------------------------------------

    def add_audit(self, founder_id, *, target_table, target_id, auditor, check_name,
                  verdict, findings=None):
        _check_choice(target_table, AUDIT_TARGETS, "target_table")
        _check_choice(auditor, AUDITORS, "auditor")
        _check_choice(verdict, VERDICTS, "verdict")
        _check_text(check_name, "check_name")
        with self._tx():
            self._require_founder(founder_id)
            if not self._owns(target_table, founder_id, target_id):
                raise NotFound(f"no {target_table} row {target_id!r} for this founder")
            return self._insert("audits", {
                "id": new_id(), "founder_id": founder_id, "target_table": target_table,
                "target_id": target_id, "auditor": auditor, "check_name": check_name,
                "verdict": verdict, "findings": findings, "created_at": now(),
            })

    def list_audits(self, founder_id, *, target_table=None, target_id=None):
        sql, params = "SELECT * FROM audits WHERE founder_id = ?", [founder_id]
        if target_table is not None:
            sql += " AND target_table = ?"
            params.append(target_table)
        if target_id is not None:
            sql += " AND target_id = ?"
            params.append(target_id)
        return self._rows("audits", sql + " ORDER BY created_at", tuple(params))

    # --- PR/FAQ -------------------------------------------------------------

    def add_prfaq_version(self, founder_id, *, stage, body, assumptions=None):
        _check_stage(stage)
        _check_text(body, "body")
        with self._tx():
            self._require_founder(founder_id)
            prev = self._fetch(
                "SELECT COALESCE(MAX(version), -1) AS v FROM prfaq_versions WHERE founder_id = ?", (founder_id,))
            return self._insert("prfaq_versions", {
                "id": new_id(), "founder_id": founder_id, "version": int(prev[0]["v"]) + 1,
                "stage": stage, "body": body, "assumptions": _dump(list(assumptions or [])),
                "created_at": now(),
            })

    def latest_prfaq(self, founder_id):
        return self._one("prfaq_versions",
                         "SELECT * FROM prfaq_versions WHERE founder_id = ? ORDER BY version DESC LIMIT 1",
                         (founder_id,))

    def list_prfaq_versions(self, founder_id):
        return self._rows("prfaq_versions",
                          "SELECT * FROM prfaq_versions WHERE founder_id = ? ORDER BY version", (founder_id,))

    # --- gate decisions -----------------------------------------------------

    def record_gate_decision(self, founder_id, *, stage, gate_id, decision, decided_by,
                             evidence, rationale, sean_signoff=False, routes_to_stage=None):
        _check_stage(stage)
        _check_text(gate_id, "gate_id")
        _check_choice(decision, DECISIONS, "decision")
        _check_choice(decided_by, DECIDERS, "decided_by")
        _check_text(rationale, "rationale")
        if not isinstance(evidence, list) or not evidence:
            raise LedgerError("a gate decision must cite ledger evidence; evidence is empty")
        refs = []
        for ref in evidence:
            if not isinstance(ref, dict) or set(ref) != {"table", "id"}:
                raise LedgerError(f"evidence refs are {{'table': ..., 'id': ...}}, got {ref!r}")
            _check_choice(ref["table"], EVIDENCE_TABLES, "evidence table")
            refs.append({"table": ref["table"], "id": ref["id"]})
        if decision == "pass" and stage >= SEAN_SIGNOFF_FROM_STAGE and not (
                sean_signoff and decided_by == "claude+sean"):
            raise LedgerError(f"a pass at stage {stage} needs Sean's sign-off (decided_by='claude+sean')")
        if decision == "fail":
            if routes_to_stage is None:
                raise LedgerError("a fail must say which stage the founder goes back to")
            _check_stage(routes_to_stage, "routes_to_stage")
            if routes_to_stage > stage:
                raise LedgerError("a fail cannot route a founder forward")
        elif routes_to_stage is not None:
            raise LedgerError("routes_to_stage is only for a fail")

        ts = now()
        with self._tx():
            founder = self._require_founder(founder_id)
            if founder["current_stage"] != stage:
                raise LedgerError(f"founder is at stage {founder['current_stage']}, not {stage}")
            for ref in refs:
                if not self._owns(ref["table"], founder_id, ref["id"]):
                    raise LedgerError(f"evidence {ref['table']}/{ref['id']} is not a row this founder owns")

            row = self._insert("gate_decisions", {
                "id": new_id(), "founder_id": founder_id, "stage": stage, "gate_id": gate_id,
                "decision": decision, "decided_by": decided_by, "sean_signoff": 1 if sean_signoff else 0,
                "evidence": _dump(refs), "rationale": rationale, "routes_to_stage": routes_to_stage,
                "created_at": ts,
            })

            if decision == "pass":
                self._execute(
                    "UPDATE stage_progress SET status = 'passed', passed_at = ?, updated_at = ?"
                    " WHERE founder_id = ? AND stage = ?", (ts, ts, founder_id, stage))
                next_stage = min(stage + 1, max(STAGES))
                if next_stage != stage:
                    self._open_stage(founder_id, next_stage, ts)
            else:
                next_stage = routes_to_stage
                self._open_stage(founder_id, next_stage, ts)
            self._execute("UPDATE founders SET current_stage = ?, updated_at = ? WHERE founder_id = ?",
                          (next_stage, ts, founder_id))
        return row

    def list_gate_decisions(self, founder_id, *, stage=None):
        if stage is None:
            return self._rows("gate_decisions",
                              "SELECT * FROM gate_decisions WHERE founder_id = ? ORDER BY created_at", (founder_id,))
        return self._rows("gate_decisions",
                          "SELECT * FROM gate_decisions WHERE founder_id = ? AND stage = ? ORDER BY created_at",
                          (founder_id, _check_stage(stage)))

    # --- Laya labels --------------------------------------------------------

    def add_label(self, founder_id, *, task, target_table, target_id, input_text,
                  model_label, model_version, confidence=None):
        _check_text(task, "task")
        _check_choice(target_table, LABEL_TARGETS, "target_table")
        _check_text(input_text, "input_text")
        _check_text(model_version, "model_version")
        with self._tx():
            self._require_founder(founder_id)
            if not self._owns(target_table, founder_id, target_id):
                raise NotFound(f"no {target_table} row {target_id!r} for this founder")
            return self._insert("labels", {
                "id": new_id(), "founder_id": founder_id, "task": task, "target_table": target_table,
                "target_id": target_id, "input_text": input_text, "model_label": _dump(model_label),
                "model_version": model_version,
                "confidence": None if confidence is None else float(confidence),
                "created_at": now(),
            })

    def correct_label(self, founder_id, label_id, *, corrected_label, corrected_by):
        _check_text(corrected_by, "corrected_by")
        with self._tx():
            if not self._owns("labels", founder_id, label_id):
                raise NotFound(f"no label {label_id!r} for this founder")
            self._execute(
                "UPDATE labels SET corrected_label = ?, corrected_by = ?, corrected_at = ?"
                " WHERE id = ? AND founder_id = ?",
                (_dump(corrected_label), corrected_by, now(), label_id, founder_id))
        row = self._one("labels", "SELECT * FROM labels WHERE id = ?", (label_id,))
        assert row is not None
        return row

    def list_labels(self, founder_id, *, task=None, corrected_only=False):
        sql, params = "SELECT * FROM labels WHERE founder_id = ?", [founder_id]
        if task is not None:
            sql += " AND task = ?"
            params.append(task)
        if corrected_only:
            sql += " AND corrected_at IS NOT NULL"
        return self._rows("labels", sql + " ORDER BY created_at", tuple(params))

    def export_corrected_labels(self, *, task=None):
        sql, params = "SELECT * FROM labels WHERE corrected_at IS NOT NULL", []
        if task is not None:
            sql += " AND task = ?"
            params.append(task)
        return self._rows("labels", sql + " ORDER BY corrected_at", tuple(params))

    # --- founder bundle import ----------------------------------------------

    def _encode(self, table: str, row: Row) -> dict[str, Any]:
        out = dict(row)
        for col in JSON_COLUMNS.get(table, ()):
            if out.get(col) is not None:
                out[col] = _dump(out[col])
        for col in BOOL_COLUMNS.get(table, ()):
            if out.get(col) is not None:
                out[col] = 1 if out[col] else 0
        return out

    def import_founder_rows(self, founder_id, tables, *, replace=False):
        _check_text(founder_id, "founder_id")
        unknown = set(tables) - set(BUNDLE_TABLES)
        if unknown:
            raise LedgerError(f"unknown ledger tables in import: {', '.join(sorted(unknown))}")
        if len(tables.get("founders", [])) != 1:
            raise LedgerError("an import carries exactly one founders row")
        for table in BUNDLE_TABLES:
            pk = "founder_id" if table == "founders" else "id"
            for row in tables.get(table, []):
                if not isinstance(row, dict):
                    raise LedgerError(f"{table}: rows are objects, got {type(row).__name__}")
                extra = set(row) - set(TABLE_COLUMNS[table])
                if extra:
                    raise LedgerError(
                        f"{table}: unknown columns {', '.join(sorted(extra))} - the bundle is from a newer schema")
                if row.get("founder_id") != founder_id:
                    raise LedgerError(f"{table} row {row.get(pk)!r} belongs to another founder")
                if not isinstance(row.get(pk), str) or not row[pk]:
                    raise LedgerError(f"{table}: every row needs a string {pk}")

        counts = {t: {"inserted": 0, "unchanged": 0} for t in BUNDLE_TABLES}
        conflicts: list[str] = []
        with self._tx():
            if replace and self.get_founder(founder_id) is not None:
                self.delete_founder(founder_id)
            for table in BUNDLE_TABLES:
                pk = "founder_id" if table == "founders" else "id"
                for row in tables.get(table, []):
                    existing = self._one(table, f"SELECT * FROM {table} WHERE {pk} = ?", (row[pk],))
                    if existing is not None:
                        wanted = {c: row.get(c) for c in existing}
                        if existing["founder_id"] != founder_id:
                            conflicts.append(f"{table}/{row[pk]} is owned by another founder")
                        elif existing != wanted:
                            diff = sorted(c for c in existing if existing[c] != wanted[c])
                            conflicts.append(f"{table}/{row[pk]} differs locally ({', '.join(diff)})")
                        else:
                            counts[table]["unchanged"] += 1
                        continue
                    values = self._encode(table, row)
                    cols = ", ".join(values)
                    marks = ", ".join("?" for _ in values)
                    try:
                        self._execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(values.values()))
                    except LedgerError:
                        raise
                    except Exception as exc:
                        raise LedgerError(f"{table}/{row[pk]} was rejected by the database: {exc}") from exc
                    counts[table]["inserted"] += 1
            if conflicts:
                raise LedgerError(
                    "import refused, nothing written. Rows already present with different content:\n  "
                    + "\n  ".join(conflicts)
                    + "\nre-run with replace to discard this founder's local rows and load the bundle")

            refs = [("audits", r["id"], r["target_table"], r["target_id"]) for r in tables.get("audits", [])]
            refs += [("labels", r["id"], r["target_table"], r["target_id"]) for r in tables.get("labels", [])]
            for r in tables.get("gate_decisions", []):
                refs += [("gate_decisions", r["id"], e.get("table"), e.get("id")) for e in r["evidence"]]
            for table, row_id, target_table, target_id in refs:
                if target_table not in EVIDENCE_TABLES or not self._owns(target_table, founder_id, target_id):
                    raise LedgerError(
                        f"{table}/{row_id} points at {target_table}/{target_id}, which this founder does not own")
        return counts
