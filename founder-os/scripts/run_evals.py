#!/usr/bin/env python3
"""run_evals.py - score FounderOS skills and cards against plain Claude.

    run_evals.py validate
        Check every fixture set: shape, ids, labels that contradict their own
        rules, turn and paragraph numbers. No model calls. CI runs this.

    run_evals.py subjects [--laya]
        List what would be evaluated and the files each arm loads.

    run_evals.py live --run-id 2026-09-26-live [--model sonnet] [--repeats 2]
                      [--jobs 6] [--laya-url http://127.0.0.1:8765]
                      [--workdir DIR] [--sets interviews,profiles] [--notes "..."]
        The live eval. Calls `claude -p` once per arm, item and repeat, from an
        empty working directory with no tools and no MCP servers. Writes
        evals/results/<run-id>.json (the summary the lint reads),
        evals/results/<run-id>.calls.jsonl (every answer, raw) and
        evals/results/<run-id>.md (the table). Commit all three, wins and
        null results alike.

    run_evals.py report --run-id RUN
        Rewrite the markdown from a results file.

Manual only: it costs money and needs a logged-in claude CLI. CI never runs it.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR))

from founder_eval import runner  # noqa: E402
from founder_eval.sets import SET_NAMES, validate_set  # noqa: E402
from founder_eval.subjects import subjects  # noqa: E402

RESULTS = PLUGIN_DIR / "evals" / "results"


def cmd_validate(args) -> int:
    problems = [p for name in SET_NAMES for p in validate_set(name)]
    if problems:
        print(f"FAIL: {len(problems)} fixture problem(s)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"OK: {len(SET_NAMES)} fixture sets are valid")
    return 0


def cmd_subjects(args) -> int:
    for s in subjects(laya=args.laya):
        print(f"{s.id}  [{s.kind}, stage {s.stage}, set {s.fixture_set}{', auditor ' + s.auditor if s.auditor else ''}]")
        for f in s.files:
            print(f"    {f}")
    return 0


def cmd_live(args) -> int:
    if cmd_validate(args):
        return 1
    workdir = pathlib.Path(args.workdir) if args.workdir else pathlib.Path(tempfile.mkdtemp(prefix="fos-evals-"))
    subject_list = subjects(laya=bool(args.laya_url))
    model = runner.claude_cli(args.model, workdir)
    sets = args.sets.split(",") if args.sets else None
    out = runner.run(subject_list, model, repeats=args.repeats, jobs=args.jobs, laya_url=args.laya_url,
                     sets=sets, log=lambda s: print(s, flush=True))
    models = sorted({c["model"] for c in out["calls"] if c["model"]})
    results = runner.summarise(out["calls"], subject_list, run_id=args.run_id, mode="live",
                               model=", ".join(models) or args.model, repeats=args.repeats,
                               laya=args.laya_url and "laya 0.3.20 via Router.predict", notes=args.notes or "")
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{args.run_id}.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n",
                                                 encoding="utf-8")
    with (RESULTS / f"{args.run_id}.calls.jsonl").open("w", encoding="utf-8") as fh:
        for c in sorted(out["calls"], key=lambda c: (c["arm"], c["item"], c["repeat"])):
            fh.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
    (RESULTS / f"{args.run_id}.md").write_text(runner.markdown(results), encoding="utf-8")
    print(runner.markdown(results))
    return 0


def cmd_report(args) -> int:
    results = json.loads((RESULTS / f"{args.run_id}.json").read_text(encoding="utf-8"))
    (RESULTS / f"{args.run_id}.md").write_text(runner.markdown(results), encoding="utf-8")
    print(runner.markdown(results))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    p = sub.add_parser("subjects")
    p.add_argument("--laya", action="store_true")
    p.set_defaults(func=cmd_subjects)
    p = sub.add_parser("live")
    p.add_argument("--run-id", required=True)
    p.add_argument("--model", default="sonnet")
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--jobs", type=int, default=6)
    p.add_argument("--laya-url")
    p.add_argument("--workdir")
    p.add_argument("--sets")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_live)
    p = sub.add_parser("report")
    p.add_argument("--run-id", required=True)
    p.set_defaults(func=cmd_report)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
