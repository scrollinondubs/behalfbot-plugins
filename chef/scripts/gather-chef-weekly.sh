#!/usr/bin/env bash
# gather-chef-weekly.sh
# Heartbeat gate for the weekly nutrition-variety advisory.
#
# Fires the model (count=1) only when ALL of these hold:
#   1. It is the configured report day.
#   2. A real week of meals exists - at least CHEF_MIN_DAYS distinct logged days
#      in the trailing window. A report built off two logged days is noise
#      pretending to be signal, and silence is the honest output for a thin week.
#   3. The analysis has not already run this ISO week (state-file dedup).
#
# Otherwise count=0 and the model is never invoked. Steady-state cost is zero
# tokens on every other day of the week.
#
# stdout contract: JSON only, {"count": N, ...}. A bare key=value line would get
# picked up by a dispatcher's line-count fallback, so every exit path echoes
# valid JSON.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"

STATE_DIR="${CHEF_STATE_DIR:-${CHASSIS_HOME:-$HOME}/scheduled-tasks}"
STATE_FILE="$STATE_DIR/chef-weekly-state.json"
MIN_DAYS="${CHEF_MIN_DAYS:-4}"
WINDOW_DAYS="${CHEF_WINDOW_DAYS:-7}"
# 1..7 == Monday..Sunday, matching `date +%u`.
REPORT_DOW="${CHEF_REPORT_DOW:-7}"

mkdir -p "$STATE_DIR"

# --- Gate 1: report day only ---------------------------------------------
# CHEF_FORCE_DOW exists so the gate can be exercised without waiting a week.
DOW="${CHEF_FORCE_DOW:-$(date +%u)}"
if [ "$DOW" != "$REPORT_DOW" ]; then
  echo '{"count": 0, "reason": "not the configured report day"}'
  exit 0
fi

ISO_WEEK="$(date +%G-W%V)"

# --- Gate 3 (cheap, checked before the DB): already ran this ISO week? ----
if [ -f "$STATE_FILE" ]; then
  LAST_WEEK="$(STATE_FILE="$STATE_FILE" python3 -c "
import json, os
try:
    with open(os.environ['STATE_FILE'], encoding='utf-8') as fh:
        print(json.load(fh).get('last_iso_week', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")"
  if [ "$LAST_WEEK" = "$ISO_WEEK" ]; then
    echo "{\"count\": 0, \"reason\": \"already ran for $ISO_WEEK\"}"
    exit 0
  fi
fi

# --- Gate 2: a real week of meals exists ---------------------------------
# The gate and the report share one source of truth on purpose: a gate that
# computes "enough data" differently from the report it guards is a gate that
# eventually fires on a week the report cannot describe.
SUMMARY="$(python3 "$PLUGIN_ROOT/scripts/chef_plant_count.py" --days "$WINDOW_DAYS" --json 2>/dev/null || echo '')"
if [ -z "$SUMMARY" ]; then
  # DB unreachable or script error. Stay silent rather than fire on a broken read.
  echo '{"count": 0, "reason": "plant count unavailable"}'
  exit 0
fi

read_field() {
  printf '%s' "$SUMMARY" | python3 -c "
import json, sys
try:
    print(json.load(sys.stdin).get('$1', 0))
except Exception:
    print(0)
" 2>/dev/null || echo 0
}

DAYS_LOGGED="$(read_field days_logged)"
PLANTS="$(read_field distinct_plant_count)"

if [ "$DAYS_LOGGED" -lt "$MIN_DAYS" ]; then
  echo "{\"count\": 0, \"reason\": \"thin week: $DAYS_LOGGED logged days < $MIN_DAYS\", \"days_logged\": $DAYS_LOGGED}"
  exit 0
fi

echo "{\"count\": 1, \"iso_week\": \"$ISO_WEEK\", \"days_logged\": $DAYS_LOGGED, \"distinct_plant_count\": $PLANTS}"
