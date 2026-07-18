#!/usr/bin/env bash
# validate.sh - loom-vision post-setup smoke check. Exit nonzero = degraded.
# No network calls; checks tool presence and script integrity only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

for bin in node loom-dl ffmpeg ffprobe; do
  if command -v "$bin" >/dev/null 2>&1; then
    echo "[loom-vision] OK: $bin"
  else
    echo "[loom-vision] FAIL: $bin not in PATH" >&2
    fail=1
  fi
done

if bash -n "$SCRIPT_DIR/skills/loom-vision/process-loom.sh"; then
  echo "[loom-vision] OK: process-loom.sh parses"
else
  echo "[loom-vision] FAIL: process-loom.sh has syntax errors" >&2
  fail=1
fi

exit "$fail"
