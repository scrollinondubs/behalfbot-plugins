#!/usr/bin/env bash
# validate.sh - restaurant-booking post-setup smoke check. Exit nonzero = degraded.
#
# No network. Deliberately so: TheFork answers automated traffic with an
# IP-escalating block, so a validate step that probed the live site would
# degrade the operator's own access every time the chassis bootstrapped.
#
# What can be checked offline is the part that decides whether a booking gets
# submitted, and that is the part worth checking.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

for script in parse-booking-intent book-restaurant confirm-via-discord create-calendar-event; do
  if python3 -m py_compile "$SCRIPT_DIR/scripts/$script.py" >/dev/null 2>&1; then
    echo "[restaurant-booking] OK: $script.py compiles"
  else
    echo "[restaurant-booking] FAIL: $script.py has syntax errors" >&2
    fail=1
  fi
done

if [[ -x "$SCRIPT_DIR/node_modules/.bin/playwright" ]]; then
  echo "[restaurant-booking] OK: playwright $("$SCRIPT_DIR/node_modules/.bin/playwright" --version 2>/dev/null || echo '?')"
else
  echo "[restaurant-booking] FAIL: playwright not installed - run setup.sh" >&2
  fail=1
fi

# The generated Playwright script is a template string, so a syntax error in it
# is invisible until a real booking is attempted. Generate one and parse it.
if python3 "$SCRIPT_DIR/tests/test_booking_outcomes.py" >/dev/null 2>&1; then
  echo "[restaurant-booking] OK: booking outcome and refusal-path tests"
else
  echo "[restaurant-booking] FAIL: booking outcome tests failed - run" >&2
  echo "[restaurant-booking]       python3 tests/test_booking_outcomes.py for detail" >&2
  fail=1
fi

if python3 "$SCRIPT_DIR/tests/test_parse_intent.py" >/dev/null 2>&1; then
  echo "[restaurant-booking] OK: intent parser tests"
else
  echo "[restaurant-booking] FAIL: intent parser tests failed" >&2
  fail=1
fi

CONFIG="$SCRIPT_DIR/config/restaurant-booking.yaml"
if grep -qE '^confirm_user_id:\s*""\s*$' "$CONFIG" 2>/dev/null; then
  echo "[restaurant-booking] WARN: confirm_user_id is empty - any non-bot member of the" >&2
  echo "[restaurant-booking]       confirm channel can approve a booking in the operator's name." >&2
fi

exit "$fail"
