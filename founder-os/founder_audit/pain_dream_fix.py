"""Pain-Dream-Fix checker: the Laya half.

Tags every paragraph of a draft (an e-bomb, a sales page, an email) as pain,
dream or fix, and whether it pitches the product. Then checks the order: the
reader should meet their pain before any fix, and a dream before the fix.

A paragraph is premature pitching when it is a fix, or mentions the product,
before the draft has described any pain.
"""
from __future__ import annotations

import re
from typing import Any

from .common import Item, Recorder, tag_items
from .laya import LayaClient
from .questions import QuestionSet, load


def split_paragraphs(text: str) -> list[str]:
    """Blank-line separated. A markdown heading joins the paragraph under it,
    since a heading alone gives the model nothing to judge."""
    paras: list[str] = []
    pending_heading = ""
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith("#") and "\n" not in block:
            pending_heading = (pending_heading + " " + block.lstrip("# ")).strip()
            continue
        if pending_heading:
            block = pending_heading + "\n" + block
            pending_heading = ""
        paras.append(block)
    if pending_heading:
        paras.append(pending_heading)
    return paras


def audit(text: str, *, client: LayaClient, lang: str | None = None, recorder: Recorder | None = None,
          qset: QuestionSet | None = None) -> dict[str, Any]:
    qset = qset or load("pain-dream-fix")
    paras = split_paragraphs(text)
    if not paras:
        raise ValueError("the draft is empty")
    tagged = tag_items(qset, client, [Item(i + 1, p) for i, p in enumerate(paras)], lang=lang, recorder=recorder)
    rows: list[dict[str, Any]] = []
    for i, p in enumerate(paras, start=1):
        row: dict[str, Any] = {"n": i, "text": p, "section": None, "pitches_product": None}
        if tagged["mode"] == "laya":
            res = tagged["results"][i]["results"]
            row["section"] = res["section"]["value"]
            row["section_probabilities"] = res["section"].get("probabilities")
            row["pitches_product"] = res["pitches_product"]["value"]
            row["pitch_p"] = res["pitches_product"].get("p")
            if i in tagged["labels"]:
                row["label_ids"] = tagged["labels"][i]
        rows.append(row)
    out: dict[str, Any] = {
        "auditor": "pain-dream-fix",
        "question_set": tagged["question_set"],
        "mode": tagged["mode"],
        "degraded_reason": tagged["degraded_reason"],
        "paragraphs": rows,
    }
    if tagged["mode"] == "laya":
        out["summary"] = check_order(rows)
    return out


def check_order(rows: list[dict]) -> dict[str, Any]:
    def first(section: str) -> int | None:
        return next((r["n"] for r in rows if r["section"] == section), None)

    first_pain, first_dream, first_fix = first("pain"), first("dream"), first("fix")
    premature = [r["n"] for r in rows
                 if (r["section"] == "fix" or r["pitches_product"])
                 and (first_pain is None or r["n"] < first_pain)]
    fixes = sum(1 for r in rows if r["section"] == "fix")
    findings = []
    if first_pain is None:
        findings.append("no_pain")
    if first_dream is None:
        findings.append("no_dream")
    if first_fix is None:
        findings.append("no_fix")
    if premature:
        findings.append("premature_pitch")
    if first_fix is not None and first_dream is not None and first_fix < first_dream:
        findings.append("fix_before_dream")
    if rows and fixes / len(rows) > 0.5:
        findings.append("mostly_fix")
    return {
        "sequence": [r["section"] for r in rows],
        "first": {"pain": first_pain, "dream": first_dream, "fix": first_fix},
        "premature_pitch": premature,
        "findings": findings,
    }
