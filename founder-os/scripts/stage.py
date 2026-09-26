#!/usr/bin/env python3
"""stage.py - the ledger and gate calls the FounderOS stage skills make.

Every command prints JSON. The ledger comes from the same environment as
founder_ledger.open_ledger() (FOUNDER_OS_LEDGER_BACKEND and friends), and
migrations are applied on open, so a fresh SQLite file works.

Founder:
    stage.py new-founder --name "Ana" [--cohort c4] [--context '{"idea": "..."}']
    stage.py context --founder-id F
    stage.py cards --founder-id F            the current stage's cards and linked concept notes, nothing else
    stage.py rows --founder-id F --table interviews|pains|artifacts|prfaq_versions|audits
                  [--kind K] [--earlyvangelist]   read the founder's own rows

Writes (always at the founder's current stage):
    stage.py add-artifact --founder-id F --kind why_statement (--body TEXT | --body-file P) [--title T] [--meta JSON]
    stage.py add-pain --founder-id F --quote Q --source-url U --watering-hole W [--segment S] [--job J] [--tags JSON]
    stage.py add-interview --founder-id F --interviewee LABEL (--notes TEXT | --notes-file P) [--conducted-on D]
                           [--segment S] [--commitment none|time|reputation|money] [--earlyvangelist]
    stage.py add-prfaq --founder-id F (--body TEXT | --body-file P) --assumptions '["...", "..."]'

Gate:
    stage.py submit --founder-id F           assemble the submission, mark the stage gate_pending
    stage.py decide --founder-id F --decision pass|fail --rationale R [--routes-to N]
    stage.py signoff --founder-id F --verdict pass|fail --findings R     operator only (Sean)

Claude's ruling on each auditor check goes through record_audit.py against the
submission artifact: --table artifacts --id <submission_id> --auditor claude
--check check-<n>.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from founder_ledger import LedgerError, open_ledger  # noqa: E402
from founder_ledger.interface import COMMITMENTS, VERDICTS  # noqa: E402
from founder_stage import Content, GateError, assemble_submission, record_decision, record_signoff  # noqa: E402


def _text(inline: str | None, path: str | None, what: str) -> str:
    if path:
        return sys.stdin.read() if path == "-" else pathlib.Path(path).read_text(encoding="utf-8")
    if inline is None:
        raise SystemExit(f"stage.py: give --{what} or --{what}-file")
    return inline


def _json(value: str | None, what: str):
    if value is None:
        return None
    try:
        return json.loads(value)
    except ValueError as e:
        raise SystemExit(f"stage.py: --{what} is not JSON ({e})")


def _stage(ledger, founder_id: str) -> int:
    founder = ledger.get_founder(founder_id)
    if founder is None:
        raise LedgerError(f"no founder {founder_id!r}")
    return founder["current_stage"]


def _latest_by_kind(rows: list[dict]) -> list[dict]:
    latest: dict[str, dict] = {}
    for r in rows:
        if r["kind"] not in latest or r["version"] > latest[r["kind"]]["version"]:
            latest[r["kind"]] = r
    return sorted(latest.values(), key=lambda r: (r["stage"], r["kind"]))


def cmd_new_founder(ledger, content, args):
    return ledger.create_founder(args.name, cohort=args.cohort, context=_json(args.context, "context") or {})


def cmd_context(ledger, content, args):
    founder = ledger.get_founder(args.founder_id)
    if founder is None:
        raise LedgerError(f"no founder {args.founder_id!r}")
    stage = founder["current_stage"]
    skill = content.stage_skill(stage)
    gate = content.gate(stage)
    artifacts = ledger.list_artifacts(args.founder_id)
    prfaq = ledger.latest_prfaq(args.founder_id)
    return {
        "founder": founder,
        "current_stage": stage,
        "stage_skill": skill.id if skill else None,
        "gate_id": gate.id,
        "progress": ledger.list_stage_progress(args.founder_id),
        "earlier_artifacts": [
            {"id": a["id"], "stage": a["stage"], "kind": a["kind"], "version": a["version"], "title": a["title"]}
            for a in _latest_by_kind([a for a in artifacts if a["stage"] < stage])],
        "this_stage_artifacts": [
            {"id": a["id"], "kind": a["kind"], "version": a["version"], "title": a["title"]}
            for a in artifacts if a["stage"] == stage],
        "counts": {"pains": len(ledger.list_pains(args.founder_id)),
                   "interviews": len(ledger.list_interviews(args.founder_id))},
        "latest_prfaq": ({"id": prfaq["id"], "version": prfaq["version"], "stage": prfaq["stage"]}
                         if prfaq else None),
        "gate_history": [
            {"stage": d["stage"], "gate_id": d["gate_id"], "decision": d["decision"],
             "routes_to_stage": d["routes_to_stage"], "rationale": d["rationale"], "created_at": d["created_at"]}
            for d in ledger.list_gate_decisions(args.founder_id)],
    }


def cmd_cards(ledger, content, args):
    stage = _stage(ledger, args.founder_id)
    cards = content.cards(stage)
    links = sorted({link for c in cards for link in c.links()})
    return {
        "stage": stage,
        "cards": [{"id": c.id, "title": c.fields.get("title"), "path": c.rel,
                   "tier": c.fields.get("tier")} for c in cards],
        "concepts": [{"id": c.id, "title": c.fields.get("title"), "path": c.rel} for c in content.concepts(links)],
    }


def cmd_rows(ledger, content, args):
    if args.table == "interviews":
        rows = ledger.list_interviews(args.founder_id)
        return [r for r in rows if r["earlyvangelist"]] if args.earlyvangelist else rows
    if args.earlyvangelist:
        raise LedgerError("--earlyvangelist applies to interviews only")
    if args.table == "pains":
        return ledger.list_pains(args.founder_id)
    if args.table == "artifacts":
        return ledger.list_artifacts(args.founder_id, kind=args.kind)
    if args.table == "prfaq_versions":
        return ledger.list_prfaq_versions(args.founder_id)
    return ledger.list_audits(args.founder_id)


def cmd_add_artifact(ledger, content, args):
    return ledger.add_artifact(args.founder_id, stage=_stage(ledger, args.founder_id), kind=args.kind,
                               body=_text(args.body, args.body_file, "body"), title=args.title,
                               meta=_json(args.meta, "meta"))


def cmd_add_pain(ledger, content, args):
    return ledger.add_pain(args.founder_id, quote=args.quote, source_url=args.source_url,
                           watering_hole=args.watering_hole, segment=args.segment, job=args.job,
                           tags=_json(args.tags, "tags"))


def cmd_add_interview(ledger, content, args):
    return ledger.add_interview(args.founder_id, interviewee=args.interviewee,
                                notes=_text(args.notes, args.notes_file, "notes"),
                                conducted_on=args.conducted_on, segment=args.segment,
                                commitment=args.commitment, earlyvangelist=args.earlyvangelist)


def cmd_add_prfaq(ledger, content, args):
    return ledger.add_prfaq_version(args.founder_id, stage=_stage(ledger, args.founder_id),
                                    body=_text(args.body, args.body_file, "body"),
                                    assumptions=_json(args.assumptions, "assumptions"))


def cmd_submit(ledger, content, args):
    return assemble_submission(ledger, content, args.founder_id)


def cmd_decide(ledger, content, args):
    return record_decision(ledger, content, args.founder_id, decision=args.decision,
                           rationale=args.rationale, routes_to_stage=args.routes_to)


def cmd_signoff(ledger, content, args):
    if os.environ.get("FOUNDER_OS_OPERATOR") != "1":
        raise GateError("signoff is Sean's, operator-only. No skill sets FOUNDER_OS_OPERATOR=1.")
    return record_signoff(ledger, content, args.founder_id, verdict=args.verdict, findings=args.findings)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="stage.py", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new-founder")
    p.add_argument("--name", required=True)
    p.add_argument("--cohort")
    p.add_argument("--context")
    p.set_defaults(func=cmd_new_founder)

    for name, func in (("context", cmd_context), ("cards", cmd_cards), ("submit", cmd_submit)):
        p = sub.add_parser(name)
        p.add_argument("--founder-id", required=True)
        p.set_defaults(func=func)

    p = sub.add_parser("rows")
    p.add_argument("--founder-id", required=True)
    p.add_argument("--table", required=True, choices=("interviews", "pains", "artifacts", "prfaq_versions", "audits"))
    p.add_argument("--kind", help="artifacts only")
    p.add_argument("--earlyvangelist", action="store_true", help="interviews only")
    p.set_defaults(func=cmd_rows)

    p = sub.add_parser("add-artifact")
    p.add_argument("--founder-id", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--body")
    p.add_argument("--body-file")
    p.add_argument("--title")
    p.add_argument("--meta")
    p.set_defaults(func=cmd_add_artifact)

    p = sub.add_parser("add-pain")
    p.add_argument("--founder-id", required=True)
    p.add_argument("--quote", required=True)
    p.add_argument("--source-url", required=True)
    p.add_argument("--watering-hole", required=True)
    p.add_argument("--segment")
    p.add_argument("--job")
    p.add_argument("--tags")
    p.set_defaults(func=cmd_add_pain)

    p = sub.add_parser("add-interview")
    p.add_argument("--founder-id", required=True)
    p.add_argument("--interviewee", required=True, help="a pseudonymous label, never a name or contact")
    p.add_argument("--notes")
    p.add_argument("--notes-file")
    p.add_argument("--conducted-on")
    p.add_argument("--segment")
    p.add_argument("--commitment", choices=COMMITMENTS, default="none")
    p.add_argument("--earlyvangelist", action="store_true")
    p.set_defaults(func=cmd_add_interview)

    p = sub.add_parser("add-prfaq")
    p.add_argument("--founder-id", required=True)
    p.add_argument("--body")
    p.add_argument("--body-file")
    p.add_argument("--assumptions", required=True)
    p.set_defaults(func=cmd_add_prfaq)

    p = sub.add_parser("decide")
    p.add_argument("--founder-id", required=True)
    p.add_argument("--decision", required=True, choices=("pass", "fail"))
    p.add_argument("--rationale", required=True)
    p.add_argument("--routes-to", type=int, help="fail only; defaults to the gate's fail_routes_to")
    p.set_defaults(func=cmd_decide)

    p = sub.add_parser("signoff")
    p.add_argument("--founder-id", required=True)
    p.add_argument("--verdict", required=True, choices=VERDICTS)
    p.add_argument("--findings", required=True)
    p.set_defaults(func=cmd_signoff)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    content = Content()
    try:
        with open_ledger(migrate=True) as ledger:
            out = args.func(ledger, content, args)
    except (LedgerError, GateError, LookupError, RuntimeError) as e:
        print(f"stage.py {args.command}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
