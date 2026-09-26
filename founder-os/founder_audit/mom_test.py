"""Mom Test interview auditor: the Laya half.

Splits a transcript into numbered turns, marks each as founder or interviewee,
has Laya tag every turn, adds the checks a pattern does better than a model,
and summarises. Claude turns the result into the feedback report, citing turn
numbers (skills/founder-os-mom-test-auditor/SKILL.md).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .common import Item, Recorder, tag_items
from .laya import LayaClient
from .questions import QuestionSet, load

FOUNDER_ALIASES = {"me", "i", "founder", "interviewer", "q", "question", "host"}
INTERVIEWEE_ALIASES = {"a", "answer", "interviewee", "customer", "guest"}

_SPEAKER = re.compile(
    r"^\s*(?:\[?\(?\d{1,2}:\d{2}(?::\d{2})?\)?\]?\s*[-]?\s*)?"   # optional [00:01:23] timestamp
    r"(?:\*\*)?([A-Za-z][A-Za-z0-9 .'_-]{0,39}?)(?:\*\*)?\s*:\s*(.*)$")
_BARE_YES_NO = re.compile(
    r"^\W*(yes|yeah|yep|yup|sure|definitely|absolutely|totally|of course|for sure|"
    r"no|nope|nah|not really)\b", re.IGNORECASE)
_CLOSED_QUESTION = re.compile(
    r"(?:^|[.!?]\s+|,\s*)(do|does|did|would|will|could|can|is|are|was|were|should|have|has|"
    r"wouldn't|don't|isn't|aren't)\s+(you|it|that|this|they|there|your)\b[^?]*\?", re.IGNORECASE)

# Future tense, maybes and generalities. A "commitment" in a turn worded like
# this is talk about one, which the Mom Test counts as fluff, not a commitment.
_HYPOTHETICAL_WORDING = re.compile(
    r"\b(would|wouldn't|might|maybe|probably|someday|one day|everyone|everybody|people)\b|\w'd\b",
    re.IGNORECASE)

# Strongest first. Maps a Laya tag onto the ledger's interviews.commitment enum.
COMMITMENT_ORDER = (("commitment_money", "money"), ("commitment_intro", "reputation"),
                    ("commitment_time", "time"))


@dataclass
class Turn:
    n: int
    speaker: str
    role: str
    text: str


def split_turns(transcript: str, founder: str | None = None) -> list[Turn]:
    """Turns from "Speaker: text" lines. A line with no speaker continues the
    turn before it. The founder is the speaker named by `founder`, else the one
    labelled Me/Founder/Interviewer/Q, else whoever speaks first. Everyone else
    is an interviewee."""
    lines = transcript.splitlines()
    # A label counts as a speaker only if it opens two or more lines, so a
    # sentence like "So basically: we lost the client" inside a turn is not
    # mistaken for a new speaker. A founder named explicitly always counts.
    counts: dict[str, int] = {}
    for line in lines:
        m = _SPEAKER.match(line)
        if m:
            counts[m.group(1).strip()] = counts.get(m.group(1).strip(), 0) + 1
    known = {name for name, c in counts.items() if c >= 2 or (founder and name.lower() == founder.lower())}
    if len(known) < 2:
        known = set(counts)

    raw: list[list[str]] = []
    for line in lines:
        m = _SPEAKER.match(line)
        if m and m.group(1).strip() not in known:
            m = None
        if m:
            raw.append([m.group(1).strip(), m.group(2).strip()])
        elif line.strip() and raw:
            raw[-1][1] = (raw[-1][1] + " " + line.strip()).strip()
        elif line.strip():
            raise ValueError("the transcript must start with a 'Speaker: text' line")
    raw = [r for r in raw if r[1]]
    speakers = []
    for name, _ in raw:
        if name not in speakers:
            speakers.append(name)
    if len(speakers) < 2:
        raise ValueError(f"found {len(speakers)} speaker(s); a transcript needs the founder and at least one interviewee")

    def is_founder(name: str) -> bool:
        if founder:
            return name.lower() == founder.lower()
        return name.lower() in FOUNDER_ALIASES

    if founder and not any(is_founder(s) for s in speakers):
        raise ValueError(f"no speaker called {founder!r}; speakers are {', '.join(speakers)}")
    founder_name = next((s for s in speakers if is_founder(s)), None)
    if founder_name is None:
        non_interviewee = [s for s in speakers if s.lower() not in INTERVIEWEE_ALIASES]
        founder_name = non_interviewee[0] if non_interviewee else speakers[0]

    turns: list[Turn] = []
    for name, text in raw:
        role = "founder" if name == founder_name else "interviewee"
        if turns and turns[-1].speaker == name:
            turns[-1].text += " " + text
        else:
            turns.append(Turn(len(turns) + 1, name, role, text))
    return turns


def _questions_for(qset: QuestionSet, role: str) -> list[str]:
    return [qid for qid, q in qset.questions.items() if q.get("applies_to", "both") in (role, "both")]


def audit(transcript: str, *, client: LayaClient, founder: str | None = None, lang: str | None = None,
          recorder: Recorder | None = None, qset: QuestionSet | None = None) -> dict[str, Any]:
    qset = qset or load("mom-test")
    turns = split_turns(transcript, founder)
    items = [Item(t.n, t.text, only=_questions_for(qset, t.role)) for t in turns]
    tagged = tag_items(qset, client, items, lang=lang, recorder=recorder)

    out_turns = []
    for t in turns:
        row: dict[str, Any] = {"n": t.n, "speaker": t.speaker, "role": t.role, "text": t.text,
                               "patterns": {}, "tags": None}
        if t.role == "interviewee" and _BARE_YES_NO.match(t.text):
            row["patterns"]["bare_yes_no"] = True
        if t.role == "interviewee" and _HYPOTHETICAL_WORDING.search(t.text):
            row["patterns"]["hypothetical_wording"] = True
        if t.role == "founder" and _CLOSED_QUESTION.search(t.text):
            row["patterns"]["closed_question"] = True
        if tagged["mode"] == "laya":
            res = tagged["results"][t.n]["results"]
            row["tags"] = {qid: {"value": r["value"], "p": r.get("p"), "trust": r["trust"]}
                           for qid, r in res.items()}
            if t.n in tagged["labels"]:
                row["label_ids"] = tagged["labels"][t.n]
        out_turns.append(row)

    return {
        "auditor": "mom-test",
        "question_set": tagged["question_set"],
        "mode": tagged["mode"],
        "degraded_reason": tagged["degraded_reason"],
        "speakers": {"founder": next(t.speaker for t in turns if t.role == "founder"),
                     "interviewees": sorted({t.speaker for t in turns if t.role == "interviewee"})},
        "turns": out_turns,
        "summary": summarise(out_turns),
    }


def summarise(turns: list[dict]) -> dict[str, Any]:
    def words(role: str) -> int:
        return sum(len(t["text"].split()) for t in turns if t["role"] == role)

    fw, iw = words("founder"), words("interviewee")
    summary: dict[str, Any] = {
        "turns": len(turns),
        "founder_talk_share": round(fw / (fw + iw), 2) if fw + iw else 0.0,
        "bare_yes_no": [t["n"] for t in turns if t["patterns"].get("bare_yes_no")],
        "closed_questions": [t["n"] for t in turns if t["patterns"].get("closed_question")],
    }
    if not any(t["tags"] for t in turns):
        return summary

    def tagged(qid: str, role: str | None = None) -> list[int]:
        return [t["n"] for t in turns if t["tags"] and (role is None or t["role"] == role)
                and t["tags"].get(qid, {}).get("value") is True]

    def hypothetical(t: dict) -> bool:
        return bool(t["patterns"].get("hypothetical_wording") or (t["tags"].get("hypothetical") or {}).get("value"))

    by_n = {t["n"]: t for t in turns}
    summary.update({
        "compliments": tagged("compliment"),
        "hypothetical_answers": tagged("hypothetical", "interviewee"),
        "hypothetical_questions": tagged("hypothetical", "founder"),
        "past_behaviour": tagged("past_behaviour"),
        "pitching": tagged("pitching"),
    })
    # A commitment tag only counts on a turn that is not hypothetical. The rest
    # are kept apart so Claude can say "you heard talk of paying, not a payment".
    candidates: dict[str, list[int]] = {}
    talk_only: dict[str, list[int]] = {}
    for qid, value in COMMITMENT_ORDER:
        turns_hit = tagged(qid, "interviewee")
        candidates[value] = [n for n in turns_hit if not hypothetical(by_n[n])]
        talk_only[value] = [n for n in turns_hit if hypothetical(by_n[n])]
    summary["commitment_candidates"] = candidates
    summary["commitment_talk_only"] = talk_only
    first_pitch = summary["pitching"][0] if summary["pitching"] else None
    first_fact = summary["past_behaviour"][0] if summary["past_behaviour"] else None
    summary["pitched_before_first_fact"] = bool(first_pitch and (first_fact is None or first_pitch < first_fact))
    summary["facts_vs_struck"] = {"facts": len(summary["past_behaviour"]), "struck": len(summary["compliments"])}
    summary["suggested_commitment"] = next((value for _, value in COMMITMENT_ORDER if candidates[value]), "none")
    return summary
