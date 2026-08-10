#!/usr/bin/env bash
# gather-flight-prices.sh
# Heartbeat gate for tracked flight prices.
#
# Fires the model (count>0) only when check_prices produced an alert: a fare
# crossed its target, a fare dropped further below an already-alerted target, a
# route broke, or a broken route recovered. Every other tick costs zero tokens.
#
# Two things about this gate are deliberately NOT like chef's:
#
#   1. A failure is LOUD. chef's gate stays silent when its read fails, because
#      a missing weekly report is a missing report. Here silence is a lie: a
#      price monitor that goes quiet when its scraper dies reports good news
#      forever. So a failed or unparseable check emits count=1 with an error
#      payload, and the prompt template is written to say so out loud. Do not
#      "fix" this to match chef.
#
#   2. It polls at most once per calendar day, tracked in a state file, because
#      the dispatcher ticks every 15 minutes and this gate reaches Google. Set
#      FLIGHT_SEARCH_FORCE=1 to bypass the day gate for a demo.
#
# stdout contract: JSON only, {"count": N, ...}. Every exit path echoes valid
# JSON so a dispatcher's line-count fallback cannot misread it.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"

CHASSIS_HOME="${CHASSIS_HOME:-$HOME}"
STATE_DIR="${FLIGHT_SEARCH_STATE_DIR:-$CHASSIS_HOME/scheduled-tasks}"
STATE_FILE="$STATE_DIR/flight-search-state.json"
STORE="${FLIGHT_SEARCH_STORE:-$CHASSIS_HOME/data/flight-search/tracked-routes.json}"
RESULT_FILE="$STATE_DIR/flight-search-last-check.json"

mkdir -p "$STATE_DIR" 2>/dev/null || true

emit() {
  # $1 raw JSON object
  printf '%s\n' "$1"
}

if [ ! -f "$STORE" ]; then
  emit '{"count": 0, "reason": "no tracked-route store yet"}'
  exit 0
fi

ROUTE_COUNT="$(STORE="$STORE" python3 -c "
import json, os
try:
    with open(os.environ['STORE'], encoding='utf-8') as fh:
        print(len(json.load(fh).get('routes', [])))
except Exception:
    print(-1)
" 2>/dev/null || echo -1)"

if [ "$ROUTE_COUNT" = "-1" ]; then
  # An unreadable store is a broken monitor, not an idle one.
  emit '{"count": 1, "reason": "tracked-route store is unreadable", "error": true}'
  exit 0
fi

if [ "$ROUTE_COUNT" -eq 0 ]; then
  emit '{"count": 0, "reason": "no routes tracked"}'
  exit 0
fi

TODAY="$(date +%F)"
if [ "${FLIGHT_SEARCH_FORCE:-0}" != "1" ] && [ -f "$STATE_FILE" ]; then
  LAST_DAY="$(STATE_FILE="$STATE_FILE" python3 -c "
import json, os
try:
    with open(os.environ['STATE_FILE'], encoding='utf-8') as fh:
        print(json.load(fh).get('last_poll_date', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")"
  if [ "$LAST_DAY" = "$TODAY" ]; then
    emit "{\"count\": 0, \"reason\": \"already polled on $TODAY\"}"
    exit 0
  fi
fi

CHECK_ARGS=""
if [ -n "${FLIGHT_SEARCH_SIMULATE_DROP:-}" ]; then
  CHECK_ARGS="--simulate-drop ${FLIGHT_SEARCH_SIMULATE_DROP}"
fi
if [ -n "${FLIGHT_SEARCH_SIMULATE_FAILURE:-}" ]; then
  CHECK_ARGS="$CHECK_ARGS --simulate-failure ${FLIGHT_SEARCH_SIMULATE_FAILURE}"
fi

# shellcheck disable=SC2086  # CHECK_ARGS is a deliberate word-split of flag pairs
OUTPUT="$(python3 "$PLUGIN_ROOT/scripts/flight_tools.py" check $CHECK_ARGS 2>/dev/null)"
RC=$?

if [ -z "$OUTPUT" ]; then
  emit "{\"count\": 1, \"reason\": \"check_prices produced no output (exit $RC) - the tracker is broken, not idle\", \"error\": true}"
  exit 0
fi

printf '%s\n' "$OUTPUT" > "$RESULT_FILE" 2>/dev/null || true

SUMMARY="$(RESULT_FILE="$RESULT_FILE" python3 -c "
import json, os
try:
    with open(os.environ['RESULT_FILE'], encoding='utf-8') as fh:
        data = json.load(fh)
except Exception as exc:
    print(json.dumps({'count': 1, 'reason': 'check_prices output was unparseable: %s' % exc, 'error': True}))
    raise SystemExit(0)

alerts = data.get('alerts', [])
errors = data.get('errors', [])
kinds = sorted({a.get('kind', '?') for a in alerts})
print(json.dumps({
    'count': len(alerts),
    'alert_kinds': kinds,
    'error_count': len(errors),
    'checked': data.get('checked', 0),
    'result_file': os.environ['RESULT_FILE'],
    'error': bool(errors),
    'reason': 'alerts pending' if alerts else ('routes broken but already alerted' if errors else 'no price moved'),
}))
" 2>/dev/null)"

if [ -z "$SUMMARY" ]; then
  emit '{"count": 1, "reason": "could not summarise the check result - treat as broken", "error": true}'
  exit 0
fi

STATE_FILE="$STATE_FILE" TODAY="$TODAY" python3 -c "
import json, os, datetime
path = os.environ['STATE_FILE']
try:
    with open(path, encoding='utf-8') as fh:
        state = json.load(fh)
except Exception:
    state = {}
state['last_poll_date'] = os.environ['TODAY']
state['last_poll_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
with open(path, 'w', encoding='utf-8') as fh:
    json.dump(state, fh, indent=2)
" 2>/dev/null || true

emit "$SUMMARY"
