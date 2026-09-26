#!/usr/bin/env python3
"""record_audit.py - write one audits row: a verdict on one ledger row.

The auditor skills use it for Claude's confirmed verdicts. Laya's raw tags go
to the labels table instead (audit.py --record).

auditor sean is operator-only (FOUNDER_OS_OPERATOR=1). Sean's verdicts carry
his sign-off weight at the gates, so a founder session cannot write them.

Usage:
    record_audit.py --founder-id F --table interviews --id I --auditor claude \
        --check mom_test --verdict flag --findings "turns 4, 9: compliments; no dated incident"
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from founder_ledger import LedgerError, open_ledger  # noqa: E402
from founder_ledger.interface import AUDIT_TARGETS, AUDITORS, VERDICTS  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--founder-id", required=True)
    ap.add_argument("--table", required=True, choices=AUDIT_TARGETS)
    ap.add_argument("--id", required=True)
    ap.add_argument("--auditor", required=True, choices=AUDITORS)
    ap.add_argument("--check", required=True)
    ap.add_argument("--verdict", required=True, choices=VERDICTS)
    ap.add_argument("--findings")
    args = ap.parse_args(argv)
    if args.auditor == "sean" and os.environ.get("FOUNDER_OS_OPERATOR") != "1":
        print("record_audit.py: auditor sean is operator-only. No skill sets FOUNDER_OS_OPERATOR=1.",
              file=sys.stderr)
        return 1
    with open_ledger() as ledger:
        try:
            row = ledger.add_audit(args.founder_id, target_table=args.table, target_id=args.id,
                                   auditor=args.auditor, check_name=args.check, verdict=args.verdict,
                                   findings=args.findings)
        except LedgerError as e:
            print(f"record_audit.py: {e}", file=sys.stderr)
            return 1
    print(json.dumps({"audit_id": row["id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
