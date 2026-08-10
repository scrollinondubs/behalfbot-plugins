#!/usr/bin/env bash
# validate.sh - accommodation-search post-setup smoke check. Exit nonzero = degraded.
#
# No credentials needed and no network touched. That is the point: the plugin
# ships with response fixtures, so the whole path - MCP transport, OAuth
# short-circuit, error translation, the empty-result guard - can be exercised
# end to end on a machine that has never had an Amadeus account.
#
# What it deliberately does NOT prove is that live credentials work against the
# live API. Nothing offline can prove that. Run the demo against real keys for
# that, which is the one step left for the install's owner:
#
#   AMADEUS_CLIENT_ID=... AMADEUS_CLIENT_SECRET=... \
#     python3 scripts/demo.py --city LON

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

check() {
  # $1 label, then the command
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "[accommodation-search] OK: $label"
  else
    echo "[accommodation-search] FAIL: $label" >&2
    fail=1
  fi
}

check "python3 on PATH" command -v python3

for script in "$PLUGIN_DIR"/scripts/*.py "$PLUGIN_DIR"/tests/*.py; do
  check "$(basename "$script") parses" python3 -m py_compile "$script"
done

check "every import is standard library" python3 "$PLUGIN_DIR/scripts/check_stdlib_only.py" "$PLUGIN_DIR"

# The dependency policy, checked from the other direction: requirements.txt
# must stay free of actual requirements, and if that ever changes it needs a
# lockfile beside it.
if grep -E -q '^[[:space:]]*[A-Za-z0-9_.-]+[[:space:]]*(==|>=|<=|~=|>|<)' "$PLUGIN_DIR/requirements.txt"; then
  if [ -f "$PLUGIN_DIR/requirements.lock" ]; then
    echo "[accommodation-search] OK: dependencies declared and a lockfile is committed"
  else
    echo "[accommodation-search] FAIL: requirements.txt declares a dependency with no" >&2
    echo "[accommodation-search]       committed lockfile beside it." >&2
    fail=1
  fi
else
  echo "[accommodation-search] OK: no third-party dependencies to pin"
fi

# Nothing in this plugin may write a credential anywhere. The only legitimate
# source is the process environment.
if grep -rn -E '(AMADEUS_CLIENT_ID|AMADEUS_CLIENT_SECRET)[[:space:]]*=[[:space:]]*["'"'"'][^"'"'"']' \
     "$PLUGIN_DIR" --include='*.py' --include='*.sh' --include='*.json' 2>/dev/null; then
  echo "[accommodation-search] FAIL: a credential looks hard-coded above." >&2
  fail=1
else
  echo "[accommodation-search] OK: no hard-coded credential"
fi

if grep -rn -E 'dotenv|\.env\b' "$PLUGIN_DIR" --include='*.py' 2>/dev/null | grep -v '^.*#'; then
  echo "[accommodation-search] FAIL: something reads credentials from a file." >&2
  fail=1
else
  echo "[accommodation-search] OK: credentials come from the environment only"
fi

# Search only. A booking call is the one thing this plugin must never grow, and
# Amadeus exposes one at /v2/booking/hotel-orders.
if grep -rn -E 'booking/hotel-orders|hotel-bookings' "$PLUGIN_DIR" \
     --include='*.py' --include='*.json' | grep -v -E '(never|not|no) book'; then
  echo "[accommodation-search] FAIL: something references a booking endpoint." >&2
  fail=1
else
  echo "[accommodation-search] OK: no booking endpoint referenced"
fi

# The plugin's tests, run as part of validation rather than only in CI. They
# need no network and no credentials, so there is no reason not to.
for suite in "$PLUGIN_DIR"/tests/test_*.py; do
  check "$(basename "$suite")" python3 "$suite"
done

# End to end over the real stdio transport, on canned data. A search that works
# must exit 0; a search that comes back empty must exit 2, because an empty
# result is an error in this plugin and a validate that accepted 0 there would
# be checking nothing.
demo_state="$(mktemp -d)"
export ACCOMMODATION_STATE_DIR="$demo_state"

if python3 "$PLUGIN_DIR/scripts/demo.py" --fixtures happy --city LON >/dev/null 2>&1; then
  echo "[accommodation-search] OK: offline demo returns results end to end"
else
  echo "[accommodation-search] FAIL: offline demo did not return results" >&2
  fail=1
fi

set +e
python3 "$PLUGIN_DIR/scripts/demo.py" --fixtures empty --city LON >/dev/null 2>&1
empty_rc=$?
python3 "$PLUGIN_DIR/scripts/demo.py" --fixtures quota --city LON >/dev/null 2>&1
quota_rc=$?
set -e
rm -rf "$demo_state"

if [ "$empty_rc" -eq 2 ]; then
  echo "[accommodation-search] OK: an empty search surfaces as an error, not as a result"
else
  echo "[accommodation-search] FAIL: empty search exited $empty_rc, expected 2" >&2
  fail=1
fi

if [ "$quota_rc" -eq 2 ]; then
  echo "[accommodation-search] OK: an exhausted quota surfaces as an error"
else
  echo "[accommodation-search] FAIL: quota-exhausted search exited $quota_rc, expected 2" >&2
  fail=1
fi

if [ -n "${AMADEUS_CLIENT_ID:-}" ] && [ -n "${AMADEUS_CLIENT_SECRET:-}" ]; then
  echo "[accommodation-search] NOTE: credentials are set. Nothing here calls the live API -"
  echo "[accommodation-search]       run scripts/demo.py without --fixtures to confirm live."
else
  echo "[accommodation-search] NOTE: no credentials set. Everything above was checked offline;"
  echo "[accommodation-search]       live search needs AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET."
fi

exit "$fail"
