"""Shared by the auditors: tag a list of items, degrade as one unit, record labels."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from founder_ledger import Ledger

from . import labels
from .laya import LayaClient, LayaUnavailable
from .questions import QuestionSet
from .tagger import Tagger


@dataclass
class Recorder:
    """Where to write labels. target is the ledger row every label hangs on:
    the interviews row for a transcript, the artifacts row for an e-bomb."""
    ledger: Ledger
    founder_id: str
    target_table: str
    target_id: str


@dataclass
class Item:
    key: Any
    text: str
    only: list[str] | None = None
    runtime: dict | None = None
    # When the item is its own ledger row (a pain quote), label it there
    # instead of on the recorder's shared target.
    target: tuple[str, str] | None = None


def tag_items(qset: QuestionSet, client: LayaClient, items: list[Item], *, lang: str | None = None,
              recorder: Recorder | None = None) -> dict[str, Any]:
    """Tag every item, or none. On LayaUnavailable the whole run becomes a
    Claude-only audit: a report half from Laya and half from Claude is harder
    to trust than either, and a timed-out server rarely comes back mid-run.

    Returns {"mode", "degraded_reason", "results": {key: tagger output}, "labels": {key: {qid: id}}}.
    """
    out: dict[str, Any] = {"question_set": qset.ref, "mode": "laya", "degraded_reason": None,
                           "results": {}, "labels": {}}
    if not client.configured:
        out.update(mode="claude-only", degraded_reason="LAYA_URL is not set")
        return out
    tagger = Tagger(qset, client)
    try:
        for item in items:
            out["results"][item.key] = tagger.tag(item.text, lang=lang, only=item.only, runtime=item.runtime)
    except LayaUnavailable as e:
        out.update(mode="claude-only", degraded_reason=str(e), results={})
        return out
    if recorder is not None:
        for item in items:
            table, target_id = item.target or (recorder.target_table, recorder.target_id)
            ids = labels.record(recorder.ledger, recorder.founder_id, qset, target_table=table,
                                target_id=target_id, input_text=item.text,
                                results=out["results"][item.key]["results"])
            out["labels"][item.key] = ids
    return out
