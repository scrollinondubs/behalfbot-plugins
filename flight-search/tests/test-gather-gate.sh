#!/usr/bin/env bash
# test-gather-gate.sh - offline checks on the heartbeat gate.
#
# Self-contained: no network, no model, stdlib python3 only. The gate never
# reaches Google in any case exercised here, because every case ends before the
# check runs or is driven through --simulate-*.
#
# What matters most is the last two cases. chef's gate stays silent when its
# read fails; this one must shout, because a price monitor that goes quiet when
# its source dies reports good news forever.

set -uo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$TEST_DIR")"
GATHER="$PLUGIN_ROOT/scripts/gather-flight-prices.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PASS=0
FAIL=0

check() {
  # $1 label, $2 expected count, $3 raw JSON output
  local label="$1" expected="$2" output="$3" actual
  actual="$(printf '%s' "$output" | python3 -c "
import json, sys
try:
    print(json.load(sys.stdin).get('count'))
except Exception as exc:
    print('unparseable: %s' % exc)
" 2>/dev/null)"
  if [ "$actual" = "$expected" ]; then
    printf 'PASS  %s (count=%s)\n' "$label" "$actual"
    PASS=$((PASS + 1))
  else
    printf 'FAIL  %s: expected count=%s, got %s\n' "$label" "$expected" "$actual"
    printf '      output: %s\n' "$output"
    FAIL=$((FAIL + 1))
  fi
}

run_gather() {
  FLIGHT_SEARCH_STORE="$WORK/store.json" \
  FLIGHT_SEARCH_STATE_DIR="$WORK/state" \
  CHASSIS_HOME="$WORK" \
  FLIGHT_SEARCH_FORCE=1 \
  "$@" bash "$GATHER" 2>/dev/null
}

# 1. No store at all: nothing has ever been tracked. Idle, not broken.
check "no store yet" 0 "$(run_gather)"

# 2. A store with no routes. Same.
printf '{"schema": 1, "routes": []}\n' > "$WORK/store.json"
check "store with no routes" 0 "$(run_gather)"

# 3. An unreadable store is a BROKEN tracker, not an idle one.
printf '{ this is not json\n' > "$WORK/store.json"
check "corrupt store shouts" 1 "$(run_gather)"

# 4. A tracked route whose price is forced below its target: exactly one alert.
python3 - "$WORK/store.json" <<'PY'
import json, sys
store = {
    "schema": 1,
    "routes": [
        {
            "id": "TEST-ROUTE-1",
            "label": "test route",
            "created_utc": "2026-08-01T00:00:00+00:00",
            "query": {"origin": "LIS", "destination": "JFK", "date": "2099-09-09"},
            "target_price": 400.0,
            "currency": "EUR",
            "status": "new",
            "consecutive_errors": 0,
            "history": [],
            "last_alert": None,
            "last_error": None,
            "last_checked_utc": None,
        }
    ],
}
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(store, fh)
PY
check "simulated drop alerts once" 1 "$(run_gather env FLIGHT_SEARCH_SIMULATE_DROP=TEST-ROUTE-1=250)"

# 5. The same price again is not news.
check "same price stays silent" 0 "$(run_gather env FLIGHT_SEARCH_SIMULATE_DROP=TEST-ROUTE-1=250)"

# 6. A broken scraper alerts. This is the case the whole plugin exists for.
check "simulated scraper failure shouts" 1 "$(run_gather env FLIGHT_SEARCH_SIMULATE_FAILURE=all)"

# 7. The day gate: without FLIGHT_SEARCH_FORCE the second run of a day is free.
# The priming run is forced through the simulated-failure path so this case
# still reaches no network.
FLIGHT_SEARCH_STORE="$WORK/store.json" FLIGHT_SEARCH_STATE_DIR="$WORK/state" CHASSIS_HOME="$WORK" \
  FLIGHT_SEARCH_SIMULATE_FAILURE=all bash "$GATHER" >/dev/null 2>&1
DAY_GATED="$(FLIGHT_SEARCH_STORE="$WORK/store.json" FLIGHT_SEARCH_STATE_DIR="$WORK/state" \
  CHASSIS_HOME="$WORK" bash "$GATHER" 2>/dev/null)"
check "second run of the day is free" 0 "$DAY_GATED"

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
