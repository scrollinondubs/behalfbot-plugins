"""Label capture: every Laya tag a user accepts or rejects becomes a
fine-tuning example in the ledger's labels table.

One row per (item, question). The task is "<set task>.<question id>", e.g.
"mom_test.compliment", which is the shape a Laya fine-tune consumes: one text,
one question, one answer. A row per item with a dict of tags would make
accepting one tag and rejecting another on the same turn a partial update.

Flow:
  1. an auditor run with recording on calls record() for every tag it made.
     The row holds the model's answer and no correction.
  2. the founder (or Sean, or Claude with the founder's say-so) accepts or
     rejects a tag. Both call correct_label: accept writes the model's own
     answer back as the correction, reject writes the right answer. Either way
     corrected_at is set, and only rows with corrected_at are exported.
     A tag nobody reviewed is never a training example.

model_version is "laya:<checkpoint>:<set name>@<set version>", so the export
can put the exact question text next to every example.
"""
from __future__ import annotations

import pathlib
from typing import Any

from founder_ledger import Ledger, LedgerError, NotFound

from .questions import LAYA_DIR, QuestionSet, QuestionSetError, load


def model_version(checkpoint: str, qset: QuestionSet) -> str:
    return f"laya:{checkpoint}:{qset.ref}"


def parse_model_version(value: str) -> tuple[str, str, str] | None:
    """(checkpoint, set name, set version), or None for a foreign format."""
    parts = value.split(":")
    if len(parts) != 3 or parts[0] != "laya" or "@" not in parts[2]:
        return None
    name, _, version = parts[2].partition("@")
    return parts[1], name, version


def record(ledger: Ledger, founder_id: str, qset: QuestionSet, *, target_table: str,
           target_id: str, input_text: str, results: dict[str, dict]) -> dict[str, str]:
    """Write one unreviewed label per tag. Returns {question id: label id}.

    Questions whose options are filled in at run time (the founder's own job
    clusters) are not recorded: without the options the example cannot be
    replayed, and those options differ per founder."""
    ids: dict[str, str] = {}
    for qid, r in results.items():
        if qset.runtime_key(qid) is not None:
            continue
        row = ledger.add_label(
            founder_id, task=f"{qset.task}.{qid}", target_table=target_table, target_id=target_id,
            input_text=input_text, model_label=r["value"],
            model_version=model_version(r["checkpoint"], qset), confidence=r.get("confidence"))
        ids[qid] = row["id"]
    return ids


def _find(ledger: Ledger, founder_id: str, label_id: str) -> dict:
    for row in ledger.list_labels(founder_id):
        if row["id"] == label_id:
            return row
    raise NotFound(f"no label {label_id!r} for this founder")


def accept(ledger: Ledger, founder_id: str, label_id: str, *, by: str) -> dict:
    row = _find(ledger, founder_id, label_id)
    return ledger.correct_label(founder_id, label_id, corrected_label=row["model_label"], corrected_by=by)


def reject(ledger: Ledger, founder_id: str, label_id: str, *, by: str, value: Any = None) -> dict:
    """A yes/no tag flips when no value is given. Any other tag needs the right answer."""
    row = _find(ledger, founder_id, label_id)
    model = row["model_label"]
    if value is None:
        if not isinstance(model, bool):
            raise LedgerError(f"label {label_id} is {model!r}; rejecting it needs the right answer as value")
        value = not model
    if value == model:
        raise LedgerError(f"label {label_id}: the correction {value!r} is what the model said; accept it instead")
    return ledger.correct_label(founder_id, label_id, corrected_label=value, corrected_by=by)


def export_rows(ledger: Ledger, *, task: str | None = None,
                laya_dir: pathlib.Path = LAYA_DIR) -> tuple[list[dict], list[str]]:
    """The fine-tune set: every reviewed label across all founders, with the
    question inlined. Cross-tenant, so operator-only. founder_id and the ledger
    row the label hangs on are left out: a training example needs neither.
    Returns (rows, warnings)."""
    sets: dict[str, QuestionSet | None] = {}
    warnings: list[str] = []
    rows = []
    for label in ledger.export_corrected_labels(task=task):
        parsed = parse_model_version(label["model_version"])
        question = None
        checkpoint = set_ref = None
        if parsed:
            checkpoint, name, version = parsed
            set_ref = f"{name}@{version}"
            if name not in sets:
                try:
                    sets[name] = load(name, laya_dir)
                except (OSError, ValueError, QuestionSetError):
                    sets[name] = None
            qset = sets[name]
            qid = label["task"].split(".", 1)[-1]
            if qset is not None and qset.version == version and qid in qset.questions:
                question = qset.question_text(qid)
            else:
                warnings.append(f"label {label['id']}: question text for {set_ref} {qid} is not in the "
                                "current question sets; exported without it")
        rows.append({
            "label_id": label["id"],
            "task": label["task"],
            "question_set": set_ref,
            "checkpoint": checkpoint,
            "question": question,
            "input_text": label["input_text"],
            "model_label": label["model_label"],
            "corrected_label": label["corrected_label"],
            "agreed": label["corrected_label"] == label["model_label"],
            "confidence": label["confidence"],
            "corrected_at": label["corrected_at"],
        })
    return rows, warnings
