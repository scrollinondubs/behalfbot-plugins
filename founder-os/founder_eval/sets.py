"""Fixture sets: how each is shown to the model, what it must answer, and how
the answer is scored against the expected labels.

Every arm of an eval (plain Claude, a card, an auditor skill, a stage skill)
gets the same task text and the same item. Only the material loaded before the
task differs. So the task text carries the definitions a fair judge needs, and
what an arm adds on top of plain Claude is the method, not the answer key.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any, Callable

from founder_audit.mom_test import split_turns
from founder_audit.pain_dream_fix import split_paragraphs

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = PLUGIN_DIR / "evals" / "fixtures"

COMMITMENTS = ("none", "time", "reputation", "money")


# --- rendering ----------------------------------------------------------------

def item_text(set_name: str, item: dict, root: pathlib.Path = FIXTURES) -> str:
    """The raw input, from the item or its file."""
    if "input_file" in item:
        return (root / item["input_file"]).read_text(encoding="utf-8")
    raw = item["input"]
    return raw if isinstance(raw, str) else json.dumps(raw, indent=1, ensure_ascii=False)


def render(set_name: str, item: dict, root: pathlib.Path = FIXTURES) -> str:
    text = item_text(set_name, item, root)
    if set_name == "interviews":
        turns = split_turns(text, "Founder")
        return "\n".join(f"[{t.n}] {t.speaker} ({t.role}): {t.text}" for t in turns)
    if set_name == "ebombs":
        return "\n\n".join(f"[{n}] {p}" for n, p in enumerate(split_paragraphs(text), start=1))
    return text


TASKS: dict[str, str] = {
    "interviews": """Audit this customer discovery interview. Turns are numbered in square brackets.

Definitions:
- A fact turn is an interviewee turn that describes something specific the interviewee did or that happened to them in the past (a dated or countable incident, money or time already spent, a tool tried).
- A struck turn is an interviewee turn that is mainly a compliment, a prediction or hypothetical ("I would", "probably", "maybe"), or a generic claim about other people or the industry.
- A turn can be neither.
- commitment is the strongest thing the interviewee actually agreed to do next: "money" (a payment, deposit or paid pilot agreed now), "reputation" (a concrete introduction to someone), "time" (a scheduled meeting, trial or session with a date or day), or "none". Talking about what they would pay is not a commitment. "Keep me posted" is none.
- pitched_before_first_fact is true if the founder described their product or solution before the interviewee's first fact turn, or pitched and there was no fact turn at all.
- verdict: "pass" if there are at least two fact turns, the founder did not pitch before the first fact, and commitment is not "none"; "fail" if there are no fact turns; otherwise "flag".

Reply with only a JSON object:
{"verdict": "pass|flag|fail", "commitment": "none|time|reputation|money", "pitched_before_first_fact": true|false, "fact_turns": [turn numbers], "struck_turns": [turn numbers]}""",

    "profiles": """Here are a founder's notes on one prospect after a discovery call. Judge each of Steve Blank's earlyvangelist criteria from what the notes show the person has done or said about their own situation:
- has_problem: the person has this problem in their own work, not someone else's
- knows_problem: the person already sees it as a problem and says so themselves
- searching: the person is actively looking for a fix now (trying products, asking around, a booked demo)
- has_workaround: the person has built or paid for a stopgap (a spreadsheet, a script, a paid helper)
- has_budget: the person already spends money on it, or controls or can get a budget for it
earlyvangelist is true when at least four of the five are true.

Reply with only a JSON object:
{"has_problem": true|false, "knows_problem": true|false, "searching": true|false, "has_workaround": true|false, "has_budget": true|false, "earlyvangelist": true|false}""",

    "ebombs": """Here is a draft e-bomb or sales page. Paragraphs are numbered in square brackets. Label each paragraph by what it mainly does for the reader:
- "pain": a problem, frustration or cost the reader has today, in their terms
- "dream": what the reader's work or life looks like once the problem is gone, without naming a product
- "fix": a solution, method, product, feature, offer, price or call to action
Also say:
- product_paragraphs: the paragraphs that mention or promote the writer's own product, service or offer (teaching a method is not a product)
- premature_pitch: true if any fix paragraph or product paragraph comes before the first pain paragraph
- fix_before_dream: true if the first fix paragraph comes before the first dream paragraph (false if there is no dream paragraph)

Reply with only a JSON object:
{"sections": ["pain|dream|fix", ...one per paragraph in order], "premature_pitch": true|false, "fix_before_dream": true|false, "product_paragraphs": [paragraph numbers]}""",

    "pain-logs": """Here is a founder's pain log from Sales Safari research: quotes collected from places their audience talks. Review it the way a gate reviewer would.

Flag every entry that should not count as evidence:
- it is not the author's own pain: advice to others, an announcement or promotion, or a general opinion
- it is paraphrased: written in the founder's words rather than quoted from the author
- its source_url is missing, or points to a channel, forum or thread index rather than the post itself
- it was prompted by the founder: posted by founder_handle, or a reply to a question or poll the founder posted
- it duplicates an earlier entry

Then the verdict: "pass" if, counting only unflagged entries, at least one job has entries from at least 5 distinct authors across at least 2 different watering holes; otherwise "fail".

Reply with only a JSON object:
{"flagged": [entry ids], "verdict": "pass|fail"}""",

    "assumptions": """Here is the assumption list from a founder's first PR/FAQ, with the idea it belongs to.

- falsifiable: the assumptions written so that one concrete result could prove them false. Each names who, a number and a threshold. Vague or taste-based claims are not falsifiable.
- riskiest: the one assumption (from the whole list) that would sink the business if it turned out false, which should be tested first. Rank by the cost of being wrong, not by how easy it is to test.

Reply with only a JSON object:
{"falsifiable": [assumption ids], "riskiest": "assumption id"}""",

    "audiences": """Here is a founder's stage 1 audience line and first bowling-pin segment.

- audience_is_people: true if the audience line describes people by the recurring work or job they do, not a market ("SMBs"), a demographic ("Gen Z") or the product itself
- pin_is_narrower: true if the bowling-pin segment is a strict, reachable subset of that audience whose members plausibly know each other, not a rename, a wider group, or a region of a market
- verdict: "pass" only if both are true, otherwise "fail"

Reply with only a JSON object:
{"audience_is_people": true|false, "pin_is_narrower": true|false, "verdict": "pass|fail"}""",
}


# --- scoring ------------------------------------------------------------------

def f1(pred: Any, gold: list, ignore: list | None = None) -> float:
    ignore_set = set(ignore or [])
    try:
        p = {x for x in pred if x not in ignore_set}
    except TypeError:
        return 0.0
    g = {x for x in gold if x not in ignore_set}
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    tp = len(p & g)
    if tp == 0:
        return 0.0
    precision, recall = tp / len(p), tp / len(g)
    return 2 * precision * recall / (precision + recall)


def _eq(a: Any, b: Any) -> float:
    return 1.0 if a == b else 0.0


def _ints(values: Any) -> list:
    out = []
    for v in values if isinstance(values, list) else []:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            out.append(v)
    return out


def score_interviews(pred: dict, item: dict) -> dict[str, float]:
    exp, ignore = item["expected"], item.get("ignore_turns", [])
    return {
        "verdict": _eq(pred.get("verdict"), exp["verdict"]),
        "commitment": _eq(pred.get("commitment"), exp["commitment"]),
        "pitched_before_first_fact": _eq(pred.get("pitched_before_first_fact"), exp["pitched_before_first_fact"]),
        "fact_turns": f1(_ints(pred.get("fact_turns")), exp["fact_turns"], ignore),
        "struck_turns": f1(_ints(pred.get("struck_turns")), exp["struck_turns"], ignore),
    }


CRITERIA = ("has_problem", "knows_problem", "searching", "has_workaround", "has_budget")


def score_profiles(pred: dict, item: dict) -> dict[str, float]:
    exp = item["expected"]
    return {
        "criteria": sum(_eq(pred.get(c), exp[c]) for c in CRITERIA) / len(CRITERIA),
        "earlyvangelist": _eq(pred.get("earlyvangelist"), exp["earlyvangelist"]),
    }


def score_ebombs(pred: dict, item: dict) -> dict[str, float]:
    exp = item["expected"]
    got = pred.get("sections") if isinstance(pred.get("sections"), list) else []
    gold = exp["sections"]
    return {
        "sections": sum(1 for i, s in enumerate(gold) if i < len(got) and got[i] == s) / len(gold),
        "premature_pitch": _eq(pred.get("premature_pitch"), exp["premature_pitch"]),
        "fix_before_dream": _eq(pred.get("fix_before_dream"), exp["fix_before_dream"]),
        "product_paragraphs": f1(_ints(pred.get("product_paragraphs")), exp["product_paragraphs"]),
    }


def score_pain_logs(pred: dict, item: dict) -> dict[str, float]:
    exp = item["expected"]
    flagged = pred.get("flagged") if isinstance(pred.get("flagged"), list) else []
    return {
        "verdict": _eq(pred.get("verdict"), exp["verdict"]),
        "flagged": f1([str(x) for x in flagged], exp["flagged"]),
    }


def score_assumptions(pred: dict, item: dict) -> dict[str, float]:
    exp = item["expected"]
    fals = pred.get("falsifiable") if isinstance(pred.get("falsifiable"), list) else []
    return {
        "falsifiable": f1([str(x) for x in fals], exp["falsifiable"]),
        "riskiest": _eq(pred.get("riskiest"), exp["riskiest"]),
    }


def score_audiences(pred: dict, item: dict) -> dict[str, float]:
    exp = item["expected"]
    return {k: _eq(pred.get(k), exp[k]) for k in ("audience_is_people", "pin_is_narrower", "verdict")}


SCORERS: dict[str, Callable[[dict, dict], dict[str, float]]] = {
    "interviews": score_interviews,
    "profiles": score_profiles,
    "ebombs": score_ebombs,
    "pain-logs": score_pain_logs,
    "assumptions": score_assumptions,
    "audiences": score_audiences,
}


def score(set_name: str, pred: dict | None, item: dict) -> tuple[float, dict[str, float]]:
    """(item score in 0..1, per-component scores). An unparseable answer scores 0."""
    if not isinstance(pred, dict):
        return 0.0, {}
    parts = SCORERS[set_name](pred, item)
    return sum(parts.values()) / len(parts), parts


# --- loading and validation ---------------------------------------------------

def load_set(set_name: str, root: pathlib.Path = FIXTURES) -> dict:
    return json.loads((root / f"{set_name}.json").read_text(encoding="utf-8"))


def validate_set(set_name: str, root: pathlib.Path = FIXTURES) -> list[str]:
    """Problems with one fixture set: shape, ids, labels that contradict their
    own rules, and turn or paragraph numbers that do not exist."""
    problems: list[str] = []
    try:
        data = load_set(set_name, root)
    except (OSError, ValueError) as e:
        return [f"{set_name}: cannot load ({e})"]
    where = f"{set_name}.json"
    if data.get("set") != set_name:
        problems.append(f"{where}: set is {data.get('set')!r}")
    items = data.get("items")
    if not isinstance(items, list) or len(items) < 4:
        return problems + [f"{where}: needs at least 4 items"]
    ids = [i.get("id") for i in items]
    if len(set(ids)) != len(ids):
        problems.append(f"{where}: duplicate item ids")
    for item in items:
        tag = f"{where}:{item.get('id')}"
        if not item.get("note"):
            problems.append(f"{tag}: every item says why it has the labels it has (note)")
        try:
            rendered = render(set_name, item, root)
        except (OSError, ValueError, KeyError) as e:
            problems.append(f"{tag}: cannot render ({e})")
            continue
        exp = item.get("expected", {})
        problems += [f"{tag}: {p}" for p in _check_expected(set_name, item, exp, rendered, root)]
        best, _ = score(set_name, exp, item)
        if best != 1.0:
            problems.append(f"{tag}: the expected answer does not score 1.0 against itself ({best})")
    return problems


def _check_expected(set_name: str, item: dict, exp: dict, rendered: str, root: pathlib.Path) -> list[str]:
    out: list[str] = []
    if set_name == "interviews":
        turns = split_turns(item_text(set_name, item, root), "Founder")
        interviewee = {t.n for t in turns if t.role == "interviewee"}
        for key in ("fact_turns", "struck_turns"):
            bad = [n for n in exp.get(key, []) if n not in interviewee]
            if bad:
                out.append(f"{key} {bad} are not interviewee turns")
        if set(exp.get("fact_turns", [])) & set(exp.get("struck_turns", [])):
            out.append("a turn cannot be both a fact and struck")
        if exp.get("commitment") not in COMMITMENTS:
            out.append(f"commitment {exp.get('commitment')!r}")
        facts = len(exp.get("fact_turns", []))
        want = ("fail" if facts == 0 else "pass" if facts >= 2 and not exp.get("pitched_before_first_fact")
                and exp.get("commitment") != "none" else "flag")
        if exp.get("verdict") != want:
            out.append(f"verdict {exp.get('verdict')!r} contradicts the rule, which gives {want!r}")
    elif set_name == "profiles":
        met = sum(1 for c in CRITERIA if exp.get(c) is True)
        if exp.get("earlyvangelist") is not (met >= 4):
            out.append(f"earlyvangelist {exp.get('earlyvangelist')} with {met} criteria met")
    elif set_name == "ebombs":
        n = len(split_paragraphs(item_text(set_name, item, root)))
        secs = exp.get("sections", [])
        if len(secs) != n:
            out.append(f"{len(secs)} section labels for {n} paragraphs")
        if any(s not in ("pain", "dream", "fix") for s in secs):
            out.append("section labels are pain, dream or fix")
        first = {s: next((i + 1 for i, x in enumerate(secs) if x == s), None) for s in ("pain", "dream", "fix")}
        prod = set(exp.get("product_paragraphs", []))
        premature = any((secs[i] == "fix" or (i + 1) in prod) and (first["pain"] is None or i + 1 < first["pain"])
                        for i in range(len(secs)))
        if exp.get("premature_pitch") is not premature:
            out.append(f"premature_pitch contradicts the labels (rule gives {premature})")
        fbd = first["fix"] is not None and first["dream"] is not None and first["fix"] < first["dream"]
        if exp.get("fix_before_dream") is not fbd:
            out.append(f"fix_before_dream contradicts the labels (rule gives {fbd})")
    elif set_name == "pain-logs":
        entries = item["input"]["entries"]
        eids = [e["id"] for e in entries]
        if set(exp.get("flagged", [])) - set(eids):
            out.append("flagged ids that are not entries")
        kept = [e for e in entries if e["id"] not in set(exp.get("flagged", []))]
        by_job: dict[str, tuple[set, set]] = {}
        for e in kept:
            authors, holes = by_job.setdefault(e["job"], (set(), set()))
            authors.add(e["author"])
            holes.add(e["watering_hole"])
        ok = any(len(a) >= 5 and len(h) >= 2 for a, h in by_job.values())
        if exp.get("verdict") != ("pass" if ok else "fail"):
            out.append(f"verdict contradicts the stopping rule over unflagged entries (rule gives {ok})")
    elif set_name == "assumptions":
        ids = set(item["input"]["assumptions"])
        if set(exp.get("falsifiable", [])) - ids or exp.get("riskiest") not in ids:
            out.append("expected names an assumption id that is not in the list")
    elif set_name == "audiences":
        want = "pass" if exp.get("audience_is_people") and exp.get("pin_is_narrower") else "fail"
        if exp.get("verdict") != want:
            out.append(f"verdict contradicts the rule ({want})")
    return out


SET_NAMES = tuple(TASKS)
