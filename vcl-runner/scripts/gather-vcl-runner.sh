#!/usr/bin/env bash
# gather-vcl-runner.sh
# Heartbeat gate for the VCL runner.
#
# Unlike most gates, the work happens here: `vcl-runner tick` claims the
# student's queued jobs from the Vibecode Lisboa Hub, runs each
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

# The dispatcher sources .env.baked or .env without `set -a`, so a key added
# by `vcl-runner setup` after the container booted is a shell variable
# the dispatcher can see but this process cannot. Read it from the same files
# the dispatcher does. The value is exported for the runner and never echoed.
ENV_HOME="${CUSTOMER_HOME:-${CHASSIS_HOME:-}}"

read_env_value() {
  # $1 variable name. Prints the last assignment in .env.baked, else .env.
  local f line value
  [ -n "$ENV_HOME" ] || return 1
  for f in "$ENV_HOME/.env.baked" "$ENV_HOME/.env"; do
    [ -f "$f" ] || continue
    line="$(grep -E "^(export[[:space:]]+)?$1=" "$f" 2>/dev/null | tail -n 1)"
    [ -n "$line" ] || continue
    value="${line#*=}"
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    printf '%s' "$value"
    return 0
  done
  return 1
}

if [ -z "${FOUNDER_OS_AGENT_KEY:-}" ]; then
  FOUNDER_OS_AGENT_KEY="$(read_env_value FOUNDER_OS_AGENT_KEY || true)"
fi
if [ -z "${FOUNDER_OS_AGENT_BASE_URL:-}" ]; then
  FOUNDER_OS_AGENT_BASE_URL="$(read_env_value FOUNDER_OS_AGENT_BASE_URL || true)"
fi
if [ -z "${RMAPI_BIN:-}" ]; then
  RMAPI_BIN="$(read_env_value RMAPI_BIN || true)"
fi
export FOUNDER_OS_AGENT_KEY FOUNDER_OS_AGENT_BASE_URL RMAPI_BIN

OUTPUT="$(python3 "$PLUGIN_ROOT/bin/vcl-runner" tick)"
RC=$?

if [ -z "$OUTPUT" ]; then
  printf '{"count": 1, "error": true, "reason": "vcl-runner tick produced no output (exit %s) - the runner is broken, not idle"}\n' "$RC"
  exit 0
fi

printf '%s\n' "$OUTPUT"
