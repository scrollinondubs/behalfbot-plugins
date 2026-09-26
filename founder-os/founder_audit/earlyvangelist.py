"""Earlyvangelist qualifier: the Laya half.

Blank's five criteria as noul questions over what one interviewee said. Four
or more yes answers escalate the interview to Claude, then Sean. Nothing here
sets interviews.earlyvangelist: the ledger has no call to change it after the
interview is written, and the stage 3 gate wants a human on that call anyway.
"""
from __future__ import annotations

from typing import Any

from .common import Item, Recorder, tag_items
from .laya import LayaClient
from .mom_test import split_turns
from .questions import QuestionSet, load


def interviewee_text(transcript: str, founder: str | None = None) -> str:
    """Only what the interviewees said. The founder's pitch describes the
    problem too, and would score as if the interviewee had said it."""
    return "\n\n".join(t.text for t in split_turns(transcript, founder) if t.role == "interviewee")


def audit(text: str, *, client: LayaClient, transcript: bool = False, founder: str | None = None,
          lang: str | None = None, recorder: Recorder | None = None,
          qset: QuestionSet | None = None) -> dict[str, Any]:
    qset = qset or load("earlyvangelist")
    body = interviewee_text(text, founder) if transcript else text.strip()
    tagged = tag_items(qset, client, [Item("interview", body)], lang=lang, recorder=recorder)
    escalate_at = int(qset.data.get("escalate_at", 4))
    out: dict[str, Any] = {
        "auditor": "earlyvangelist",
        "question_set": tagged["question_set"],
        "mode": tagged["mode"],
        "degraded_reason": tagged["degraded_reason"],
        "escalate_at": escalate_at,
        "criteria": None,
        "met": None,
        "escalate": None,
    }
    if tagged["mode"] != "laya":
        out["criteria_to_check"] = {qid: q["instructions"] for qid, q in qset.questions.items()}
        return out
    res = tagged["results"]["interview"]["results"]
    out["criteria"] = {qid: {k: r[k] for k in ("value", "p", "trust", "excerpt") if k in r}
                       for qid, r in res.items()}
    met = [qid for qid, r in res.items() if r["value"] is True]
    out["met"] = met
    out["escalate"] = len(met) >= escalate_at
    if "interview" in tagged["labels"]:
        out["label_ids"] = tagged["labels"]["interview"]
    return out
