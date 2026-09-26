"""Gate submissions and gate decisions.

The flow a stage skill follows:

1. assemble_submission: count the gate's `evidence:` minimums in the ledger,
   write a `gate_submission` artifact holding the counts, the auditor checks
   and the ledger refs, and mark the stage gate_pending.
2. Claude rules on every auditor check in the gate spec, one `audits` row per
   check against the submission artifact (record_audit.py, auditor claude).
3. From stage 3 on, Sean signs off: an `audits` row by sean, check
   `gate_signoff`, against the same submission (record_signoff, operator-only).
4. record_decision: pass or fail. A pass is refused unless every minimum is
   met now, every check has a Claude ruling and none of them is a fail, and,
   from stage 3, Sean's sign-off is on the submission. A fail routes the
   founder to the gate's fail_routes_to unless the decision names an earlier
   stage.

The founder is never a decider. Nothing here takes the founder's word for a
row that is not in the ledger, and the ledger itself refuses a stage 3+ pass
without Sean's sign-off.
"""
from __future__ import annotations

from founder_ledger.interface import SEAN_SIGNOFF_FROM_STAGE

from .content import Content, bullets, section
from .evidence import count_requirements, parse_evidence

SUBMISSION_KIND = "gate_submission"
SIGNOFF_CHECK = "gate_signoff"


class GateError(ValueError):
    """The gate step was refused. The message says what is missing."""


def _founder(ledger, founder_id: str) -> dict:
    founder = ledger.get_founder(founder_id)
    if founder is None:
        raise GateError(f"no founder {founder_id!r}")
    return founder


def _progress(ledger, founder_id: str, stage: int) -> dict:
    for row in ledger.list_stage_progress(founder_id):
        if row["stage"] == stage:
            return row
    raise GateError(f"stage {stage} has no progress row")


def _refs(ledger, founder_id: str, counts: list[dict]) -> list[dict]:
    refs: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(table: str, row_id: str) -> None:
        if (table, row_id) not in seen:
            seen.add((table, row_id))
            refs.append({"table": table, "id": row_id})

    for c in counts:
        for row_id in c["ids"]:
            add(c["table"], row_id)
            for a in ledger.list_audits(founder_id, target_table=c["table"], target_id=row_id):
                add("audits", a["id"])
    return refs


def checks_for(gate) -> list[dict]:
    out = []
    for n, text in enumerate(bullets(section(gate.body, "Auditor checks")), start=1):
        tail = text[text.rfind("("):] if "(" in text else ""
        out.append({"n": n, "check": f"check-{n}", "text": text,
                    "who": "laya-then-claude" if "Laya" in tail else "claude"})
    return out


def assemble_submission(ledger, content: Content, founder_id: str) -> dict:
    founder = _founder(ledger, founder_id)
    stage = founder["current_stage"]
    if _progress(ledger, founder_id, stage)["status"] == "passed":
        raise GateError(f"stage {stage} is already passed")
    gate = content.gate(stage)
    counts = count_requirements(ledger, founder_id, parse_evidence(gate.fields.get("evidence")))
    missing = [c["requirement"] for c in counts if not c["ok"]]
    checks = checks_for(gate)
    meta = {
        "gate_id": gate.id, "stage": stage, "signoff": gate.fields.get("signoff"),
        "fail_routes_to": int(str(gate.fields.get("fail_routes_to"))),
        "requirements": counts, "missing": missing, "checks": checks,
        "evidence": _refs(ledger, founder_id, counts),
        "failure_routing": bullets(section(gate.body, "Failure routing")),
    }
    lines = [f"Gate submission for {gate.id} (stage {stage}).", "", "Minimums:"]
    lines += [f"- {c['requirement']}: have {c['have']}, need {c['need']}{'' if c['ok'] else ' - MISSING'}"
              for c in counts]
    lines += ["", f"Checks to rule on: {len(checks)}. Sign-off: {meta['signoff']}."]
    row = ledger.add_artifact(founder_id, stage=stage, kind=SUBMISSION_KIND, body="\n".join(lines),
                              title=f"Gate submission: {gate.id}", meta=meta)
    ledger.mark_gate_pending(founder_id, stage)
    return {"submission_id": row["id"], "ready": not missing, **meta}


def _latest_submission(ledger, founder_id: str, stage: int, gate_id: str) -> dict:
    subs = [a for a in ledger.list_artifacts(founder_id, stage=stage, kind=SUBMISSION_KIND)
            if a["meta"].get("gate_id") == gate_id]
    if not subs:
        raise GateError(f"no gate submission for {gate_id}; run submit first")
    sub = max(subs, key=lambda a: a["version"])
    earlier = ledger.list_gate_decisions(founder_id, stage=stage)
    if earlier and max(d["created_at"] for d in earlier) >= sub["created_at"]:
        raise GateError(f"the latest submission for {gate_id} was already decided; run submit again")
    return sub


def record_signoff(ledger, content: Content, founder_id: str, *, verdict: str, findings: str) -> dict:
    """Sean's sign-off on the pending submission. The CLI only calls this for the operator."""
    founder = _founder(ledger, founder_id)
    stage = founder["current_stage"]
    gate = content.gate(stage)
    sub = _latest_submission(ledger, founder_id, stage, gate.id)
    return ledger.add_audit(founder_id, target_table="artifacts", target_id=sub["id"], auditor="sean",
                            check_name=SIGNOFF_CHECK, verdict=verdict, findings=findings)


def record_decision(ledger, content: Content, founder_id: str, *, decision: str, rationale: str,
                    routes_to_stage: int | None = None) -> dict:
    founder = _founder(ledger, founder_id)
    stage = founder["current_stage"]
    if _progress(ledger, founder_id, stage)["status"] != "gate_pending":
        raise GateError(f"stage {stage} is not gate_pending; the stage skill hands over with submit first")
    gate = content.gate(stage)
    sub = _latest_submission(ledger, founder_id, stage, gate.id)
    rulings = ledger.list_audits(founder_id, target_table="artifacts", target_id=sub["id"])
    claude = [a for a in rulings if a["auditor"] == "claude"]
    sean = [a for a in rulings if a["auditor"] == "sean" and a["check_name"] == SIGNOFF_CHECK]

    counts = count_requirements(ledger, founder_id, parse_evidence(gate.fields.get("evidence")))
    evidence = [{"table": "artifacts", "id": sub["id"]}]
    evidence += [{"table": "audits", "id": a["id"]} for a in rulings]
    evidence += [r for r in _refs(ledger, founder_id, counts) if r not in evidence]

    decided_by, signed = "claude", False
    if decision == "pass":
        missing = [c["requirement"] for c in counts if not c["ok"]]
        if missing:
            raise GateError(f"a pass needs every minimum in the gate spec; missing: {', '.join(missing)}")
        ruled = {a["check_name"] for a in claude}
        unruled = [c["check"] for c in sub["meta"]["checks"] if c["check"] not in ruled]
        if unruled:
            raise GateError(f"Claude has not ruled on {', '.join(unruled)}; one audits row per check first")
        failed = sorted(a["check_name"] for a in claude if a["verdict"] == "fail")
        if failed:
            raise GateError(f"a pass with failed checks ({', '.join(failed)}) is a fail")
        if stage >= SEAN_SIGNOFF_FROM_STAGE:
            latest = max(sean, key=lambda a: a["created_at"]) if sean else None
            if latest is None or latest["verdict"] != "pass":
                raise GateError(f"stage {stage} needs Sean's sign-off on submission {sub['id']} before a pass")
            decided_by, signed = "claude+sean", True
        routes_to_stage = None
    elif decision == "fail":
        if routes_to_stage is None:
            routes_to_stage = int(str(gate.fields.get("fail_routes_to")))
    else:
        raise GateError("decision is pass or fail")

    return ledger.record_gate_decision(
        founder_id, stage=stage, gate_id=gate.id, decision=decision, decided_by=decided_by,
        evidence=evidence, rationale=rationale, sean_signoff=signed, routes_to_stage=routes_to_stage)
