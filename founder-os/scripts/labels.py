#!/usr/bin/env python3
"""labels.py - accept or reject Laya tags, one founder at a time.

Every accept and every reject is written to the ledger's labels table as a
correction, and every corrected row is a fine-tuning example. A tag nobody
reviews is never exported.

Usage:
    labels.py pending --founder-id F [--task mom_test.compliment]
    labels.py accept  --founder-id F --by WHO LABEL_ID [LABEL_ID ...]
    labels.py reject  --founder-id F --by WHO LABEL_ID [--value JSON]

A rejected yes/no tag flips on its own. Any other tag needs --value, the right
answer as JSON: --value '"dream"' or --value 2.

--by is who made the call: the founder's id, "sean", or "claude" when the
founder asked Claude to apply their decision.

The cross-founder export for fine-tuning is export_labels.py, operator-only.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from founder_audit import labels  # noqa: E402
from founder_ledger import LedgerError, open_ledger  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("command", choices=("pending", "accept", "reject"))
    ap.add_argument("label_ids", nargs="*")
    ap.add_argument("--founder-id", required=True)
    ap.add_argument("--by")
    ap.add_argument("--task")
    ap.add_argument("--value", help="reject: the right answer, as JSON")
    args = ap.parse_args(argv)

    with open_ledger() as ledger:
        if args.command == "pending":
            rows = [r for r in ledger.list_labels(args.founder_id, task=args.task) if r["corrected_at"] is None]
            out = [{k: r[k] for k in ("id", "task", "target_table", "target_id", "input_text",
                                      "model_label", "confidence")} for r in rows]
            json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
            print()
            return 0
        if not args.by:
            ap.error(f"{args.command} needs --by")
        if not args.label_ids:
            ap.error(f"{args.command} needs at least one label id")
        if args.command == "reject" and args.value is not None and len(args.label_ids) != 1:
            ap.error("--value applies to one label at a time")
        value = json.loads(args.value) if args.value is not None else None
        try:
            for label_id in args.label_ids:
                if args.command == "accept":
                    row = labels.accept(ledger, args.founder_id, label_id, by=args.by)
                else:
                    row = labels.reject(ledger, args.founder_id, label_id, by=args.by, value=value)
                print(f"{args.command}ed {label_id} {row['task']}: {json.dumps(row['corrected_label'])}")
        except LedgerError as e:
            print(f"labels.py: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
