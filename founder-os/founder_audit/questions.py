"""Laya question sets: loading them, and picking a checkpoint per question.

A question set is laya/<name>.json. Each question holds the fields Laya reads
(type, instructions, criteria, labels) next to fields only this plugin reads:

    checkpoint   {lang: checkpoint, "default": checkpoint}. Overrides the set's
                 own map for this one question.
    aggregate    how chunk answers combine: "max" or "mean"
    threshold    a noul answer at or above it counts as yes
    trust        how far the answer can be relied on: "measured", "weak",
                 "chance", "advisory" or "unmeasured", or a map from checkpoint
                 to one of those
    applies_to   mom-test only: "founder", "interviewee" or "both"

Only the Laya fields go over the wire. laya-serve validates question
definitions and rejects keys it does not know.
"""
from __future__ import annotations

import json
import pathlib
import unicodedata
from typing import Any

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
LAYA_DIR = PLUGIN_DIR / "laya"

WIRE_FIELDS = ("type", "instructions", "criteria", "labels")
QUESTION_TYPES = ("noul", "choice", "score")
CHECKPOINTS = ("english", "multilingual", "typed-decisions")
AGGREGATES = ("max", "mean")
TRUST_LEVELS = ("measured", "weak", "chance", "advisory", "unmeasured")
APPLIES_TO = ("founder", "interviewee", "both")
RUNTIME_PREFIX = "runtime:"


class QuestionSetError(ValueError):
    pass


class QuestionSet:
    def __init__(self, data: dict, source: str = "<dict>") -> None:
        problems = validate(data)
        if problems:
            raise QuestionSetError(f"{source}: " + "; ".join(problems))
        self.data = data
        self.name: str = data["name"]
        self.version: str = data["version"]
        self.task: str = data["task"]
        self.checkpoint_map: dict[str, str] = data["checkpoint"]
        self.questions: dict[str, dict] = data["questions"]

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.version}"

    def checkpoint_for(self, qid: str, lang: str | None) -> str:
        cmap = self.questions[qid].get("checkpoint") or self.checkpoint_map
        if lang and lang in cmap:
            return cmap[lang]
        return cmap["default"]

    def trust_for(self, qid: str, checkpoint: str) -> str:
        trust = self.questions[qid].get("trust", "unmeasured")
        if isinstance(trust, dict):
            return trust.get(checkpoint, "unmeasured")
        return trust

    def threshold(self, qid: str) -> float:
        return float(self.questions[qid].get("threshold", 0.5))

    def aggregate(self, qid: str) -> str:
        q = self.questions[qid]
        return q.get("aggregate") or ("mean" if q["type"] == "choice" else "max")

    def runtime_key(self, qid: str) -> str | None:
        crit = self.questions[qid].get("criteria")
        if isinstance(crit, str) and crit.startswith(RUNTIME_PREFIX):
            return crit[len(RUNTIME_PREFIX):]
        return None

    def wire_question(self, qid: str, runtime: dict | None = None) -> dict | None:
        """The definition Laya sees, or None when it needs runtime criteria
        that were not supplied."""
        q = {k: v for k, v in self.questions[qid].items() if k in WIRE_FIELDS}
        key = self.runtime_key(qid)
        if key is not None:
            value = (runtime or {}).get(key)
            if not value:
                return None
            q["criteria"] = value
        return q

    def question_text(self, qid: str) -> dict:
        """Wire fields, for inlining into a fine-tune export."""
        return {k: v for k, v in self.questions[qid].items() if k in WIRE_FIELDS}


def validate(data: Any) -> list[str]:
    """Every problem with a question set's shape. Empty when it is usable."""
    if not isinstance(data, dict):
        return ["a question set is a JSON object"]
    problems = []
    for key in ("name", "version", "task"):
        if not isinstance(data.get(key), str) or not data.get(key):
            problems.append(f"missing string field '{key}'")
    problems += _check_checkpoint_map(data.get("checkpoint"), "checkpoint")
    questions = data.get("questions")
    if not isinstance(questions, dict) or not questions:
        return problems + ["'questions' must be a non-empty object"]
    for qid, q in questions.items():
        where = f"question {qid!r}"
        if not isinstance(q, dict):
            problems.append(f"{where} must be an object")
            continue
        if q.get("type") not in QUESTION_TYPES:
            problems.append(f"{where}: type must be one of {', '.join(QUESTION_TYPES)}")
        if not isinstance(q.get("instructions"), str) or not q["instructions"].strip():
            problems.append(f"{where}: needs 'instructions'")
        crit = q.get("criteria")
        runtime = isinstance(crit, str) and crit.startswith(RUNTIME_PREFIX)
        if q.get("type") == "choice" and not runtime and not (isinstance(crit, (dict, list)) and crit):
            problems.append(f"{where}: a choice question needs criteria, or criteria: \"runtime:<key>\"")
        if q.get("type") == "score" and not (isinstance(crit, list) and crit):
            problems.append(f"{where}: a score question needs criteria as a list of levels")
        if q.get("type") == "noul" and crit is not None and not (
                isinstance(crit, dict) and {str(k).lower() for k in crit} <= {"true", "false"}):
            problems.append(f"{where}: noul criteria may only be keyed true/false")
        if "checkpoint" in q:
            problems += _check_checkpoint_map(q["checkpoint"], f"{where} checkpoint")
        if "aggregate" in q and q["aggregate"] not in AGGREGATES:
            problems.append(f"{where}: aggregate must be one of {', '.join(AGGREGATES)}")
        if "threshold" in q and not (isinstance(q["threshold"], (int, float)) and 0 < q["threshold"] < 1):
            problems.append(f"{where}: threshold must be a number between 0 and 1")
        trust = q.get("trust", "unmeasured")
        levels = trust.values() if isinstance(trust, dict) else [trust]
        if any(level not in TRUST_LEVELS for level in levels):
            problems.append(f"{where}: trust must be one of {', '.join(TRUST_LEVELS)}")
        if "applies_to" in q and q["applies_to"] not in APPLIES_TO:
            problems.append(f"{where}: applies_to must be one of {', '.join(APPLIES_TO)}")
    return problems


def _check_checkpoint_map(cmap: Any, where: str) -> list[str]:
    if not isinstance(cmap, dict) or "default" not in cmap:
        return [f"{where} must be an object with a 'default' checkpoint"]
    bad = [v for v in cmap.values() if v not in CHECKPOINTS]
    if bad:
        return [f"{where}: unknown checkpoint(s) {bad}; use {', '.join(CHECKPOINTS)}"]
    return []


def load(name: str, laya_dir: pathlib.Path = LAYA_DIR) -> QuestionSet:
    path = laya_dir / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    qset = QuestionSet(data, str(path))
    if qset.name != name:
        raise QuestionSetError(f"{path}: name {qset.name!r} does not match the file name")
    return qset


def guess_lang(text: str) -> str | None:
    """A fallback for when the caller does not say. Only script is certain:
    text in a non-Latin script is never English. Latin text returns None, which
    routes to the set's default checkpoint. Pass lang explicitly to do better."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return None
    latin = sum(1 for c in letters if "LATIN" in unicodedata.name(c, ""))
    return None if latin / len(letters) >= 0.8 else "non-latin"
