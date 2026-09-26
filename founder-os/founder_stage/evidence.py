"""A gate's machine-checkable minimums, and counting them in the ledger.

A gate spec lists its minimums in frontmatter, one requirement per list item:

    evidence: [artifacts/why_statement>=1, prfaq_versions>=1, interviews:committed>=3]

Grammar: `<table>[/<artifact kind>][:<filter>]>=<n>`.

- `artifacts/<kind>` counts artifact rows of that kind. Every stage's rows
  count, so a later gate can ask for an earlier stage's artifact.
- `pains`, `interviews`, `prfaq_versions` count rows in those tables.
- Filters: `audited` (the row has at least one audits row) on any table, and
  on interviews only `committed` (commitment is not none), `money`
  (commitment is money) and `earlyvangelist`.

These are the counts only: the part of the "Required evidence" section a query
can answer. The judgment calls stay in the gate's "Auditor checks" section, for
Claude and, from stage 3 on, Sean.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

TABLES = ("artifacts", "pains", "interviews", "prfaq_versions")
FILTERS = {
    "audited": TABLES,
    "committed": ("interviews",),
    "money": ("interviews",),
    "earlyvangelist": ("interviews",),
}
_SHAPE = re.compile(
    r"^(?P<table>[a-z_]+)(?:/(?P<kind>[a-z][a-z0-9_]*))?(?::(?P<filter>[a-z_]+))?>=(?P<n>\d+)$")


@dataclass(frozen=True)
class Requirement:
    text: str
    table: str
    kind: str | None
    filter: str | None
    minimum: int


def parse_requirement(text: str) -> Requirement:
    """Parse one requirement, or raise ValueError saying what is wrong with it."""
    m = _SHAPE.match(text.strip())
    if not m:
        raise ValueError(f"{text!r} is not <table>[/<kind>][:<filter>]>=<n>")
    table, kind, filt, n = m["table"], m["kind"], m["filter"], int(m["n"])
    if table not in TABLES:
        raise ValueError(f"{text!r}: table must be one of {', '.join(TABLES)}")
    if (table == "artifacts") != (kind is not None):
        raise ValueError(f"{text!r}: artifacts needs a /kind, and only artifacts takes one")
    if filt is not None and table not in FILTERS.get(filt, ()):
        raise ValueError(f"{text!r}: filter {filt!r} does not apply to {table}")
    if n < 1:
        raise ValueError(f"{text!r}: a minimum below 1 checks nothing")
    return Requirement(text.strip(), table, kind, filt, n)


def parse_evidence(value: object) -> list[Requirement]:
    if not isinstance(value, list) or not value:
        raise ValueError("evidence must be a non-empty inline list, e.g. evidence: [artifacts/audience>=1]")
    return [parse_requirement(str(v)) for v in value]


def _rows(ledger, founder_id: str, req: Requirement) -> list[dict]:
    if req.table == "artifacts":
        return ledger.list_artifacts(founder_id, kind=req.kind)
    if req.table == "pains":
        return ledger.list_pains(founder_id)
    if req.table == "interviews":
        return ledger.list_interviews(founder_id)
    return ledger.list_prfaq_versions(founder_id)


def count_requirements(ledger, founder_id: str, reqs: list[Requirement]) -> list[dict]:
    """One result per requirement: what it needs, what the ledger has, and the
    ids of the rows that count, so a gate decision can cite them."""
    audited: dict[str, set[str]] = {}
    out = []
    for req in reqs:
        rows = _rows(ledger, founder_id, req)
        if req.filter == "audited":
            if req.table not in audited:
                audited[req.table] = {a["target_id"] for a in ledger.list_audits(founder_id, target_table=req.table)}
            rows = [r for r in rows if r["id"] in audited[req.table]]
        elif req.filter == "committed":
            rows = [r for r in rows if r["commitment"] != "none"]
        elif req.filter == "money":
            rows = [r for r in rows if r["commitment"] == "money"]
        elif req.filter == "earlyvangelist":
            rows = [r for r in rows if r["earlyvangelist"]]
        out.append({
            "requirement": req.text, "table": req.table, "need": req.minimum, "have": len(rows),
            "ok": len(rows) >= req.minimum, "ids": [r["id"] for r in rows],
        })
    return out
