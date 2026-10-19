#!/usr/bin/env bash
# gather-safari-runner.sh
# Heartbeat gate for the FounderOS Safari runner.
#
# Unlike most gates, the work happens here: `founder-os runner tick` claims the
# student's queued painstorm and e-bomb analysis jobs from the Hub, runs each
# step through the local `claude -p` on the student's own Claude login, and
# posts the results back. The dispatcher's own model fires only when count > 0,
# which means the student has to act: the Hub rejected the agent key, or the
# claude CLI is missing. A tick with nothing queued is one HTTP request and
# zero tokens.
#
# stdout contract: JSON only, {"count": N, ...}. Every exit path echoes valid
# JSON. The runner logs to stderr, which the dispatcher appends to its log.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"

OUTPUT="$(python3 "$PLUGIN_ROOT/bin/founder-os" runner tick)"
RC=$?

if [ -z "$OUTPUT" ]; then
  printf '{"count": 1, "error": true, "reason": "founder-os runner tick produced no output (exit %s) - the runner is broken, not idle"}\n' "$RC"
  exit 0
fi

printf '%s\n' "$OUTPUT"
