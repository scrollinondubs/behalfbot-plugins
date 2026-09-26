#!/usr/bin/env python3
"""audit.py - run a FounderOS auditor and print its result as JSON.

The Laya half of every auditor skill. Claude reads the JSON and writes the
feedback. When Laya is not configured or does not answer, the result has
"mode": "claude-only" and the skill has Claude do the tagging itself.

Laya:    LAYA_URL, LAYA_API_KEY (optional), LAYA_TIMEOUT (seconds, default 20)
Ledger:  the same environment as founder_ledger.open_ledger(), needed only for
         --record and for reading input from the ledger

Usage:
    audit.py mom-test       --input transcript.txt [--founder NAME] [--lang en]
                            [--founder-id F --interview-id I [--record]]
    audit.py earlyvangelist --input notes.txt [--transcript] [--founder NAME] [--lang en]
                            [--founder-id F --interview-id I [--record]]
    audit.py pain-dream-fix --input draft.md [--lang en] [--founder-id F --artifact-id A [--record]]
    audit.py pain-tagger    --input posts.json [--jobs jobs.json] [--lang en]
    audit.py pain-log       --founder-id F [--job JOB] [--lang en] [--record]

--lang is the language of the text (en, pt, ...). Pass it: it picks the Laya
checkpoint, and English text on the english checkpoint is the only place
is_pain has been measured to work. Without it, Latin-script text goes to the
set's default checkpoint.

With --interview-id or --artifact-id and no --input, the text is read from
that ledger row. --record writes one label per tag to the ledger, for the
founder to accept or reject with labels.py.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from founder_audit import LayaClient, LayaRequestError  # noqa: E402
from founder_audit import earlyvangelist, mom_test, pain, pain_dream_fix  # noqa: E402
from founder_audit.common import Recorder  # noqa: E402


def _read(path: str | None) -> str | None:
    if path is None:
        return None
    return sys.stdin.read() if path == "-" else pathlib.Path(path).read_text(encoding="utf-8")


def _ledger():
    from founder_ledger import open_ledger
    return open_ledger()


def _row(rows: list[dict], row_id: str, what: str) -> dict:
    for r in rows:
        if r["id"] == row_id:
            return r
    raise SystemExit(f"no {what} {row_id!r} for this founder")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("auditor", choices=("mom-test", "earlyvangelist", "pain-dream-fix", "pain-tagger", "pain-log"))
    ap.add_argument("--input", help="file to read, or - for stdin")
    ap.add_argument("--lang", help="language of the text, e.g. en")
    ap.add_argument("--founder", help="the founder's speaker label in a transcript")
    ap.add_argument("--transcript", action="store_true", help="earlyvangelist: input is a transcript")
    ap.add_argument("--jobs", help="pain-tagger: JSON file of the founder's job clusters (list or {id: description})")
    ap.add_argument("--job", help="pain-log: check one job cluster only")
    ap.add_argument("--founder-id")
    ap.add_argument("--interview-id")
    ap.add_argument("--artifact-id")
    ap.add_argument("--record", action="store_true", help="write a label per tag to the ledger")
    args = ap.parse_args(argv)

    client = LayaClient()
    text = _read(args.input)
    ledger = None
    needs_ledger = args.record or args.auditor == "pain-log" or (
        text is None and (args.interview_id or args.artifact_id))
    if needs_ledger:
        if not args.founder_id:
            ap.error("--founder-id is needed for --record, pain-log, or reading from the ledger")
        ledger = _ledger()

    try:
        recorder = None
        if args.auditor in ("mom-test", "earlyvangelist"):
            if args.record and not args.interview_id:
                ap.error("--record needs --interview-id: labels hang on the interviews row")
            if text is None:
                if not args.interview_id:
                    ap.error("give --input, or --interview-id to read the interview notes")
                text = _row(ledger.list_interviews(args.founder_id), args.interview_id, "interview")["notes"]
            if args.record:
                recorder = Recorder(ledger, args.founder_id, "interviews", args.interview_id)
            if args.auditor == "mom-test":
                result = mom_test.audit(text, client=client, founder=args.founder, lang=args.lang, recorder=recorder)
            else:
                result = earlyvangelist.audit(text, client=client, transcript=args.transcript,
                                              founder=args.founder, lang=args.lang, recorder=recorder)
        elif args.auditor == "pain-dream-fix":
            if args.record and not args.artifact_id:
                ap.error("--record needs --artifact-id: labels hang on the draft's artifacts row")
            if text is None:
                if not args.artifact_id:
                    ap.error("give --input, or --artifact-id to read the draft")
                row = ledger.get_artifact(args.founder_id, args.artifact_id)
                if row is None:
                    raise SystemExit(f"no artifact {args.artifact_id!r} for this founder")
                text = row["body"]
            if args.record:
                recorder = Recorder(ledger, args.founder_id, "artifacts", args.artifact_id)
            result = pain_dream_fix.audit(text, client=client, lang=args.lang, recorder=recorder)
        elif args.auditor == "pain-tagger":
            if text is None:
                ap.error("pain-tagger needs --input: a JSON list of {id, text}")
            if args.record:
                ap.error("pain-tagger does not record: raw posts are not ledger rows. "
                         "Add the pains you keep, then run pain-log --record")
            jobs = json.loads(_read(args.jobs)) if args.jobs else None
            result = pain.rank_posts(json.loads(text), client=client, lang=args.lang, jobs=jobs)
        else:
            pains = ledger.list_pains(args.founder_id, job=args.job)
            if args.record:
                recorder = Recorder(ledger, args.founder_id, "pains", "")
            result = pain.check_log(pains, client=client, lang=args.lang, recorder=recorder)
    except LayaRequestError as e:
        print(f"audit.py: Laya rejected the request, which is a bug in the question set or the "
              f"chunking, not an outage: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"audit.py: {e}", file=sys.stderr)
        return 1
    finally:
        if ledger is not None:
            ledger.close()

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False, default=str)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
