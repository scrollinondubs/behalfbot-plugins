#!/usr/bin/env bash
# validate.sh - perplexity-research post-setup smoke check. Exit nonzero = degraded.
#
# Builds a throwaway epub from a two-line markdown file. That is the one part of
# the pipeline that can be exercised without a browser session or a network
# call, and it is also the part that silently breaks when pandoc is upgraded.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

if command -v "${RESEARCH_PANDOC_BIN:-pandoc}" >/dev/null 2>&1; then
  echo "[perplexity-research] OK: pandoc"
else
  echo "[perplexity-research] FAIL: pandoc not found" >&2
  fail=1
fi

if bash -n "$SCRIPT_DIR/scripts/build-brief-epub.sh"; then
  echo "[perplexity-research] OK: build-brief-epub.sh parses"
else
  echo "[perplexity-research] FAIL: build-brief-epub.sh has syntax errors" >&2
  fail=1
fi

if [[ "$fail" -eq 0 ]]; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  cat > "$tmp/smoke.md" <<'MD'
---
title: "Validation smoke test"
date: "1970-01-01"
---

# Validation smoke test

## 1. Section

Enough body text for pandoc to produce a non-trivial epub during validation.
MD
  if bash "$SCRIPT_DIR/scripts/build-brief-epub.sh" "$tmp/smoke.md" "$tmp/smoke.epub" >/dev/null 2>&1 \
     && [[ -s "$tmp/smoke.epub" ]]; then
    echo "[perplexity-research] OK: epub build round-trip"
  else
    echo "[perplexity-research] FAIL: epub build round-trip failed" >&2
    fail=1
  fi
fi

exit "$fail"
