#!/usr/bin/env bash
# validate.sh - parse-youtube post-setup smoke check. Exit nonzero = degraded.
# No network calls: tool presence, import health, and script syntax only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

if command -v python3 >/dev/null 2>&1; then
  echo "[parse-youtube] OK: python3"
else
  echo "[parse-youtube] FAIL: python3 not in PATH" >&2
  fail=1
fi

if python3 -c 'import youtube_transcript_api' >/dev/null 2>&1; then
  echo "[parse-youtube] OK: youtube_transcript_api importable"
else
  echo "[parse-youtube] FAIL: youtube_transcript_api not importable" >&2
  fail=1
fi

# Soft dependency. Its absence is reported, not failed - the plugin still
# returns transcripts, just without title/channel/chapters.
if command -v yt-dlp >/dev/null 2>&1; then
  echo "[parse-youtube] OK: yt-dlp"
else
  echo "[parse-youtube] WARN: yt-dlp not in PATH - metadata fields will be null" >&2
fi

if python3 -m py_compile "$SCRIPT_DIR/scripts/parse-youtube.py" >/dev/null 2>&1; then
  echo "[parse-youtube] OK: parse-youtube.py compiles"
else
  echo "[parse-youtube] FAIL: parse-youtube.py has syntax errors" >&2
  fail=1
fi

exit "$fail"
