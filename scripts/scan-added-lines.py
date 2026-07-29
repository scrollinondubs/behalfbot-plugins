#!/usr/bin/env python3
"""scan-added-lines.py - look for credential-shaped strings in a diff's ADDED lines.

Reads a unified diff on stdin and reports added lines that look like a real
secret. Scoped to added lines on purpose: rescanning the whole tree on every PR
turns a signal into background noise nobody reads, and history is a separate
problem from "did this PR bring one in".

This is a coarse net, not a secret manager. It exists because this repo is
public, takes plugin code from strangers, and a leaked key in a merged PR is
live the moment it lands - GitHub push protection catches the well-known
provider formats, and this catches the generic assignments it does not.

Deliberately dependency-free so CI needs no install step.

Usage:
    git diff origin/main...HEAD | python3 scripts/scan-added-lines.py
Exit 0 if clean, 1 if anything matched.
"""
from __future__ import annotations

import re
import sys

# Each entry: (label, compiled pattern). Kept narrow - a rule that fires on
# every third PR gets ignored, and an ignored check is worse than no check.
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}\b")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("Discord bot token", re.compile(r"\b[MNO][A-Za-z0-9_-]{23,}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    (
        "hardcoded credential assignment",
        re.compile(
            r"""(?ix)
            \b(?:api[_-]?key|secret|passwd|password|token|auth[_-]?token|access[_-]?token|bearer)
            \s*[:=]\s*
            ['"][^'"\s]{16,}['"]
            """
        ),
    ),
]

# The only two files exempt from the scan, and the reason is structural rather
# than convenient: this scanner holds the detection patterns, and its test holds
# deliberately realistic fake credentials as fixtures. Scanning either one makes
# the check fail on every PR that touches it, which is what happened the first
# time this ran in CI - seven "hits", all of them the test's own fixtures.
#
# The cost is real and worth naming: a genuine secret committed inside one of
# these two files would not be caught here. Both are kept tiny, both are named
# explicitly rather than matched by a glob, and adding to this set should feel
# like a decision. A pattern like `test_*` or `**/fixtures/**` would be an easy
# place for someone to park a real key later.
SKIP_PATHS = frozenset({
    "scripts/scan-added-lines.py",
    "scripts/test-scan-added-lines.sh",
})

# Lines that legitimately look like the above. A placeholder in an example file
# or a schema default is not a leak, and flagging them trains people to ignore
# the check.
# Note the deliberate split: word-boundary anchors work for the alphabetic
# placeholders but silently fail for the symbol-led ones, because \b needs a
# word character on one side and `${`, `<` and `$` do not have one. Keeping them
# in the same \b(?:...)\b group made `password = "${VAULT_PASSWORD}"` a false
# positive - caught by the positive-control test, which is why that test exists.
ALLOW = re.compile(
    r"""(?ix)
    (
      your[_-]?(?:key|token|secret)
    | \b(?:example|placeholder|redacted|dummy|fake|sample|changeme|xxx+)\b
    | \$\{[^}]+\}
    | \$[A-Z_]{3,}
    | <[^>]+>
    | \.\.\.
    )
    """
)


def main() -> int:
    diff = sys.stdin.read()
    hits: list[tuple[str, str, str]] = []
    current_file = "?"
    skipped: set[str] = set()

    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:]
            continue
        if not raw.startswith("+") or raw.startswith("+++"):
            continue

        if current_file in SKIP_PATHS:
            skipped.add(current_file)
            continue

        line = raw[1:]
        if ALLOW.search(line):
            continue

        for label, pat in PATTERNS:
            if pat.search(line):
                shown = line.strip()
                if len(shown) > 120:
                    shown = shown[:117] + "..."
                hits.append((current_file, label, shown))
                break

    if hits:
        print(f"FAIL: {len(hits)} credential-shaped string(s) in added lines\n")
        for path, label, shown in hits:
            print(f"  {path}")
            print(f"    {label}: {shown}\n")
        print("If this is a placeholder, make it obviously one (YOUR_API_KEY, <token>, $VAR).")
        print("If it is a real credential, it is already compromised - rotate it, do not just amend the commit.")
        return 1

    # Announce the exemption every run. A silent skip-list is how a scan quietly
    # stops covering the thing everyone assumes it covers.
    for path in sorted(skipped):
        print(f"note: {path} is exempt from this scan (holds the detection patterns or their fixtures)")

    print("OK: no credential-shaped strings in added lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
