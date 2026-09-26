#!/usr/bin/env python3
"""export_labels.py - write the Laya fine-tune set as JSONL. Operator-only.

Every reviewed label across every founder: the text, the exact question it was
asked (inlined from laya/*.json), what Laya said and what the human said.
founder_id and ledger row ids are left out.

This reads across tenants, which is why the ledger marks
export_corrected_labels operator-only (#25). It refuses to run unless
FOUNDER_OS_OPERATOR=1 is set in the environment. No skill sets that, and no
founder session should: on a self-hosted install the operator is the person
who owns the install, on VCL it is Sean.

Usage:
    FOUNDER_OS_OPERATOR=1 export_labels.py [--task mom_test.compliment] [--out labels.jsonl]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from founder_audit.labels import export_rows  # noqa: E402
from founder_ledger import open_ledger  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--task", help="one task only, e.g. pain_tag.is_pain")
    ap.add_argument("--out", help="output file (default stdout)")
    args = ap.parse_args(argv)

    if os.environ.get("FOUNDER_OS_OPERATOR") != "1":
        print("export_labels.py: refusing. The export reads every founder's labels, so it is "
              "operator-only. Set FOUNDER_OS_OPERATOR=1 if you are the operator.", file=sys.stderr)
        return 3

    with open_ledger() as ledger:
        rows, warnings = export_rows(ledger, task=args.task)
    for w in warnings:
        print(f"export_labels.py: {w}", file=sys.stderr)
    lines = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    if args.out:
        pathlib.Path(args.out).write_text(lines, encoding="utf-8")
    else:
        sys.stdout.write(lines)
    print(f"export_labels.py: {len(rows)} label(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
