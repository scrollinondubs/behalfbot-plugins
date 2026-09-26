"""The FounderOS ledger interface: the calls skills make, and nothing else.

This is the contract. The Postgres and SQLite adapters in this package implement
it, and VCL implements the same method set in TypeScript against Turso (see
docs/ledger-on-turso.md). tests/ledger_conformance.py is the executable version
of this contract, and any implementation should pass a port of it.

Conventions every implementation follows:

- Every call is scoped by founder_id. A row that belongs to another founder is
  indistinguishable from a row that does not exist. The one exception is
  export_corrected_labels, which is cross-founder by design and operator-only.
- Rows come back as plain dicts. JSON columns (context, meta, tags, assumptions,
  evidence, model_label, corrected_label) are decoded; 0/1 columns
  (earlyvangelist, sean_signoff) come back as bool.
- ids are UUID strings and timestamps are ISO-8601 UTC strings, both generated
  by the implementation rather than the database.
- Invalid input raises LedgerError. A founder_id that does not exist raises
  NotFound.
"""
from __future__ import annotations

import abc
from typing import Any

Row = dict[str, Any]

STAGES = range(0, 10)
SEAN_SIGNOFF_FROM_STAGE = 3

# Tables a gate decision may cite as evidence, and an audit may target.
EVIDENCE_TABLES = ("artifacts", "pains", "interviews", "prfaq_versions", "audits")
AUDIT_TARGETS = ("artifacts", "pains", "interviews", "prfaq_versions")
LABEL_TARGETS = ("artifacts", "pains", "interviews", "prfaq_versions")

# Every table that holds founder rows, in the order an import loads them:
# parents first, then rows other rows point at, then the rows that point.
BUNDLE_TABLES = (
    "founders", "stage_progress", "artifacts", "pains", "interviews",
    "prfaq_versions", "audits", "gate_decisions", "labels",
)

# Columns per table, as schema/migrations defines them. An import refuses a row
# with a column outside this set, which is how a bundle from a newer schema
# fails with a clear message rather than a driver error.
TABLE_COLUMNS = {
    "founders": ("founder_id", "display_name", "cohort", "current_stage", "context",
                 "created_at", "updated_at"),
    "stage_progress": ("id", "founder_id", "stage", "status", "started_at", "passed_at", "updated_at"),
    "artifacts": ("id", "founder_id", "stage", "kind", "version", "title", "body", "meta", "created_at"),
    "pains": ("id", "founder_id", "quote", "source_url", "watering_hole", "segment", "job", "tags",
              "created_at"),
    "interviews": ("id", "founder_id", "interviewee", "segment", "conducted_on", "notes", "commitment",
                   "earlyvangelist", "created_at"),
    "prfaq_versions": ("id", "founder_id", "version", "stage", "body", "assumptions", "created_at"),
    "audits": ("id", "founder_id", "target_table", "target_id", "auditor", "check_name", "verdict",
               "findings", "created_at"),
    "gate_decisions": ("id", "founder_id", "stage", "gate_id", "decision", "decided_by", "sean_signoff",
                       "evidence", "rationale", "routes_to_stage", "created_at"),
    "labels": ("id", "founder_id", "task", "target_table", "target_id", "input_text", "model_label",
               "model_version", "confidence", "corrected_label", "corrected_by", "corrected_at",
               "created_at"),
}

COMMITMENTS = ("none", "time", "reputation", "money")
AUDITORS = ("laya", "claude", "sean")
VERDICTS = ("pass", "fail", "flag")
DECISIONS = ("pass", "fail")
DECIDERS = ("claude", "claude+sean")


class LedgerError(ValueError):
    """The call was rejected: bad input, or it would break a ledger rule."""


class NotFound(LedgerError):
    """The founder, or a row scoped to that founder, does not exist."""


class Ledger(abc.ABC):
    # --- founders -----------------------------------------------------------

    @abc.abstractmethod
    def create_founder(
        self, display_name: str, *, cohort: str | None = None,
        context: dict | None = None, founder_id: str | None = None,
    ) -> Row:
        """Create a founder at stage 0, with stage 0 marked in_progress."""

    @abc.abstractmethod
    def get_founder(self, founder_id: str) -> Row | None: ...

    @abc.abstractmethod
    def update_founder_context(self, founder_id: str, context: dict) -> Row:
        """Replace the founder context blob that stage skills read first."""

    @abc.abstractmethod
    def delete_founder(self, founder_id: str) -> None:
        """Delete the founder and every row they own."""

    # --- stage progress -----------------------------------------------------

    @abc.abstractmethod
    def list_stage_progress(self, founder_id: str) -> list[Row]: ...

    @abc.abstractmethod
    def mark_gate_pending(self, founder_id: str, stage: int) -> Row:
        """The stage skill hands over to the gate auditor. Only the current stage."""

    # --- artifacts ----------------------------------------------------------

    @abc.abstractmethod
    def add_artifact(
        self, founder_id: str, *, stage: int, kind: str, body: str,
        title: str | None = None, meta: dict | None = None,
    ) -> Row:
        """Append an artifact. Artifacts are never overwritten: each add of the
        same kind gets the next version number."""

    @abc.abstractmethod
    def get_artifact(self, founder_id: str, artifact_id: str) -> Row | None: ...

    @abc.abstractmethod
    def list_artifacts(
        self, founder_id: str, *, stage: int | None = None, kind: str | None = None,
    ) -> list[Row]: ...

    # --- pains --------------------------------------------------------------

    @abc.abstractmethod
    def add_pain(
        self, founder_id: str, *, quote: str, source_url: str | None = None,
        watering_hole: str | None = None, segment: str | None = None,
        job: str | None = None, tags: list[str] | None = None,
    ) -> Row: ...

    @abc.abstractmethod
    def list_pains(self, founder_id: str, *, job: str | None = None) -> list[Row]: ...

    # --- interviews ---------------------------------------------------------

    @abc.abstractmethod
    def add_interview(
        self, founder_id: str, *, interviewee: str, notes: str,
        conducted_on: str | None = None, segment: str | None = None,
        commitment: str = "none", earlyvangelist: bool = False,
    ) -> Row:
        """interviewee is a pseudonymous label, never a real name or contact."""

    @abc.abstractmethod
    def list_interviews(self, founder_id: str) -> list[Row]: ...

    # --- audits -------------------------------------------------------------

    @abc.abstractmethod
    def add_audit(
        self, founder_id: str, *, target_table: str, target_id: str,
        auditor: str, check_name: str, verdict: str, findings: str | None = None,
    ) -> Row:
        """Record one check against one ledger row the founder owns."""

    @abc.abstractmethod
    def list_audits(
        self, founder_id: str, *, target_table: str | None = None,
        target_id: str | None = None,
    ) -> list[Row]: ...

    # --- PR/FAQ -------------------------------------------------------------

    @abc.abstractmethod
    def add_prfaq_version(
        self, founder_id: str, *, stage: int, body: str,
        assumptions: list[str] | None = None,
    ) -> Row:
        """Append the next PR/FAQ version. The first one is version 0."""

    @abc.abstractmethod
    def latest_prfaq(self, founder_id: str) -> Row | None: ...

    @abc.abstractmethod
    def list_prfaq_versions(self, founder_id: str) -> list[Row]: ...

    # --- gate decisions -----------------------------------------------------

    @abc.abstractmethod
    def record_gate_decision(
        self, founder_id: str, *, stage: int, gate_id: str, decision: str,
        decided_by: str, evidence: list[dict], rationale: str,
        sean_signoff: bool = False, routes_to_stage: int | None = None,
    ) -> Row:
        """Record a gate decision for the founder's current stage and move them.

        evidence is a non-empty list of {"table": ..., "id": ...} refs, each to a
        row this founder owns in one of EVIDENCE_TABLES. A pass from stage 3
        onward needs sean_signoff=True and decided_by="claude+sean". A fail needs
        routes_to_stage, at or before this stage.

        A pass marks the stage passed and opens the next one. A fail sends the
        founder to routes_to_stage and reopens it.
        """

    @abc.abstractmethod
    def list_gate_decisions(self, founder_id: str, *, stage: int | None = None) -> list[Row]: ...

    # --- Laya labels --------------------------------------------------------

    @abc.abstractmethod
    def add_label(
        self, founder_id: str, *, task: str, target_table: str, target_id: str,
        input_text: str, model_label: Any, model_version: str,
        confidence: float | None = None,
    ) -> Row: ...

    @abc.abstractmethod
    def correct_label(
        self, founder_id: str, label_id: str, *, corrected_label: Any, corrected_by: str,
    ) -> Row:
        """A human correction. The corrected row becomes a fine-tuning example."""

    @abc.abstractmethod
    def list_labels(
        self, founder_id: str, *, task: str | None = None, corrected_only: bool = False,
    ) -> list[Row]: ...

    @abc.abstractmethod
    def export_corrected_labels(self, *, task: str | None = None) -> list[Row]:
        """Every corrected label across all founders: the fine-tuning set.
        Cross-tenant, so operator-only. Never expose it to a founder session."""

    # --- founder bundle import ----------------------------------------------

    @abc.abstractmethod
    def import_founder_rows(
        self, founder_id: str, tables: dict[str, list[Row]], *, replace: bool = False,
    ) -> dict[str, dict[str, int]]:
        """Load one founder's rows verbatim, ids and timestamps included.

        The one write path that does not generate ids or timestamps, because a
        founder bundle (docs/bundle-format.md) has to round-trip exactly. Export
        needs no counterpart: get_founder plus the list_* calls read every table.

        tables maps each of BUNDLE_TABLES to rows shaped like the list_* calls
        return them (JSON decoded, booleans as bool). Every row must carry this
        founder_id, and there must be exactly one founders row.

        All or nothing, in one transaction. A row whose id is already present
        with identical content is skipped, so importing the same bundle twice
        is a no-op. A row whose id is present with different content, or owned
        by another founder, is a conflict: nothing is written and LedgerError
        names the rows. replace=True deletes this founder first, then loads.

        After loading, every audit and label target and every gate evidence ref
        must point at a row this founder owns. Returns
        {table: {"inserted": n, "unchanged": m}}.
        """

    # --- lifecycle ----------------------------------------------------------

    @abc.abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
