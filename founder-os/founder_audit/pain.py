"""Pain tagger and pain-log quality check: the Laya half.

Two jobs over one question set (laya/pain-tagger.json):

rank_posts   Sales Safari pre-filter. Tags raw posts from a watering hole and
             ranks them so Claude reads the top of the funnel, not all of it.
check_log    Quality check over the founder's pains rows: is each quote a real
             pain, is it sourced and clustered, and does the log as a whole
             have enough quotes per job and enough watering holes.

Built around what #603 measured:
- is_pain only means something on the english checkpoint (AUC 0.78). On the
  multilingual one it is at chance (0.53). A result carries its trust level,
  and a chance-level is_pain never ranks posts or flags a quote. It is
  reported, marked, and left to Claude.
- money_or_workaround works on multilingual (AUC 0.84) and is used everywhere.
- intensity and the job category are advisory.
"""
from __future__ import annotations

from typing import Any

from .common import Item, Recorder, tag_items
from .laya import LayaClient
from .questions import QuestionSet, load

MIN_QUOTES_PER_JOB = 3
MIN_WATERING_HOLES = 3
MIN_QUOTE_CHARS = 25


def _runtime(jobs: dict[str, str] | list[str] | None) -> dict | None:
    return {"jobs": jobs} if jobs else None


def _usable(r: dict | None) -> bool:
    return bool(r) and r["trust"] in ("measured", "weak")


def rank_posts(posts: list[dict], *, client: LayaClient, lang: str | None = None,
               jobs: dict[str, str] | list[str] | None = None,
               qset: QuestionSet | None = None) -> dict[str, Any]:
    """posts: [{"id", "text", ...}]. Nothing is recorded: raw posts are not
    ledger rows. Record labels once a post becomes a pains row (check_log)."""
    qset = qset or load("pain-tagger")
    items = [Item(str(p["id"]), p["text"], runtime=_runtime(jobs)) for p in posts]
    tagged = tag_items(qset, client, items, lang=lang)
    out: dict[str, Any] = {"auditor": "pain-tagger", "question_set": tagged["question_set"],
                           "mode": tagged["mode"], "degraded_reason": tagged["degraded_reason"]}
    if tagged["mode"] != "laya":
        out["posts"] = [{"id": str(p["id"]), "text": p["text"]} for p in posts]
        return out
    rows = []
    for p in posts:
        res = tagged["results"][str(p["id"])]["results"]
        rows.append({"id": str(p["id"]), "text": p["text"], "tags": _compact(res)})
    is_pain_trusted = all(_usable(r["tags"].get("is_pain")) for r in rows)
    if is_pain_trusted:
        rows.sort(key=lambda r: (-r["tags"]["is_pain"]["p"], -r["tags"]["money_or_workaround"]["p"]))
        out["ranked_by"] = "is_pain, then money_or_workaround"
    else:
        rows.sort(key=lambda r: -r["tags"]["money_or_workaround"]["p"])
        out["ranked_by"] = ("money_or_workaround only: is_pain ran on a checkpoint measured at chance "
                            "for this language, so Claude reads for pain itself")
    out["posts"] = rows
    return out


def _compact(res: dict[str, dict]) -> dict[str, dict]:
    keep = ("value", "p", "score", "probabilities", "trust", "checkpoint", "chunks", "truncated", "excerpt")
    return {qid: {k: r[k] for k in keep if k in r} for qid, r in res.items()}


def check_log(pains: list[dict], *, client: LayaClient, lang: str | None = None,
              recorder: Recorder | None = None, qset: QuestionSet | None = None) -> dict[str, Any]:
    """pains: rows from ledger.list_pains. Structural checks always run; the
    Laya checks run when Laya is up. Each quote's labels hang on its own pains row."""
    qset = qset or load("pain-tagger")
    jobs = sorted({p["job"] for p in pains if p.get("job")})
    items = [Item(p["id"], p["quote"], runtime=_runtime(jobs), target=("pains", p["id"])) for p in pains]
    tagged = tag_items(qset, client, items, lang=lang, recorder=recorder)

    seen: dict[str, str] = {}
    rows = []
    for p in pains:
        issues = []
        norm = " ".join(p["quote"].lower().split())
        if norm in seen:
            issues.append(f"duplicate_of:{seen[norm]}")
        else:
            seen[norm] = p["id"]
        if len(p["quote"].strip()) < MIN_QUOTE_CHARS:
            issues.append("too_short")
        if not p.get("source_url"):
            issues.append("no_source_url")
        if not p.get("watering_hole"):
            issues.append("no_watering_hole")
        if not p.get("job"):
            issues.append("no_job")
        row: dict[str, Any] = {"id": p["id"], "quote": p["quote"], "job": p.get("job"), "issues": issues}
        if tagged["mode"] == "laya":
            res = tagged["results"][p["id"]]["results"]
            row["tags"] = _compact(res)
            is_pain = res.get("is_pain")
            if is_pain and is_pain["value"] is False:
                issues.append("not_a_pain" if _usable(is_pain) else "not_a_pain_unverified")
            cat = res.get("pain_category")
            if cat and p.get("job") and cat["value"] != p["job"]:
                issues.append(f"job_mismatch_advisory:{cat['value']}")
            if p["id"] in tagged["labels"]:
                row["label_ids"] = tagged["labels"][p["id"]]
        rows.append(row)

    per_job: dict[str, int] = {}
    for p in pains:
        if p.get("job"):
            per_job[p["job"]] = per_job.get(p["job"], 0) + 1
    holes = sorted({p["watering_hole"] for p in pains if p.get("watering_hole")})
    log: dict[str, Any] = {
        "quotes": len(pains),
        "per_job": per_job,
        "thin_jobs": sorted(j for j, n in per_job.items() if n < MIN_QUOTES_PER_JOB),
        "unclustered": sum(1 for p in pains if not p.get("job")),
        "watering_holes": holes,
        "too_few_watering_holes": len(holes) < MIN_WATERING_HOLES,
        "with_issues": sum(1 for r in rows if r["issues"]),
    }
    if tagged["mode"] == "laya" and pains:
        money = [r for r in rows if r["tags"].get("money_or_workaround", {}).get("value") is True]
        log["money_or_workaround_share"] = round(len(money) / len(pains), 2)
    return {"auditor": "pain-log", "question_set": tagged["question_set"], "mode": tagged["mode"],
            "degraded_reason": tagged["degraded_reason"], "pains": rows, "log": log}
