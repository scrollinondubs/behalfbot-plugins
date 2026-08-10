#!/usr/bin/env bash
# validate.sh - flight-search post-setup smoke check. Exit nonzero = degraded.
#
# Offline. It does not search Google, on purpose: a validate that reaches the
# network fails on a flaky connection and gets ignored, and a validate that gets
# ignored is worse than none. What it checks is that the pieces are present and
# that the failure semantics still hold - specifically that an empty result with
# a dead control route raises rather than returning "no flights", which is the
# one behaviour this plugin exists to guarantee.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

for script in scripts/flight_tools.py scripts/flight_search_mcp.py; do
  if python3 -m py_compile "$SCRIPT_DIR/$script" >/dev/null 2>&1; then
    echo "[flight-search] OK: $script compiles"
  else
    echo "[flight-search] FAIL: $script has syntax errors" >&2
    fail=1
  fi
done

if bash -n "$SCRIPT_DIR/scripts/gather-flight-prices.sh"; then
  echo "[flight-search] OK: gather-flight-prices.sh parses"
else
  echo "[flight-search] FAIL: gather-flight-prices.sh has syntax errors" >&2
  fail=1
fi

if python3 -c 'import fli' >/dev/null 2>&1; then
  VERSION="$(python3 -c 'from importlib import metadata; print(metadata.version("flights"))' 2>/dev/null || echo unknown)"
  PINNED="$(grep -E '^flights==' "$SCRIPT_DIR/requirements.txt" | head -1 | cut -d= -f3)"
  if [[ "$VERSION" == "$PINNED" ]]; then
    echo "[flight-search] OK: flights==$VERSION matches the pin"
  else
    echo "[flight-search] FAIL: flights is $VERSION, the pin is $PINNED - run setup.sh" >&2
    fail=1
  fi
else
  echo "[flight-search] FAIL: the flights package is not importable - run setup.sh" >&2
  fail=1
fi

if [[ "$fail" -eq 0 ]]; then
  if python3 - "$SCRIPT_DIR" <<'PY'; then
import sys, pathlib
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts"))
import flight_tools  # noqa: E402

flight_tools.reset_canary_cache()


def dead(query, currency, limit=5):
    return []


# An empty result while the control route is also empty must raise. If this
# ever returns instead, a broken scraper is reporting "no flights" and every
# tracked route silently reads as "no price change".
try:
    flight_tools.interpret_results([], "EUR", dead)
except flight_tools.FlightSearchError as exc:
    if exc.kind != "scraper_error":
        print(f"[flight-search] FAIL: empty + dead control raised {exc.kind}, expected scraper_error")
        raise SystemExit(1)
else:
    print("[flight-search] FAIL: empty + dead control returned instead of raising")
    raise SystemExit(1)

flight_tools.reset_canary_cache()


def healthy(query, currency, limit=5):
    import types
    from datetime import datetime
    member = lambda n: types.SimpleNamespace(name=n, value=n)  # noqa: E731
    leg = types.SimpleNamespace(
        airline=member("AA"), flight_number="1",
        departure_airport=member("JFK"), arrival_airport=member("LAX"),
        departure_datetime=datetime(2026, 9, 9, 8), arrival_datetime=datetime(2026, 9, 9, 11),
        duration=360,
    )
    return [types.SimpleNamespace(price=199.0, currency="EUR", stops=0, duration=360, legs=[leg])]


out = flight_tools.interpret_results([], "EUR", healthy)
if out.get("status") != "empty":
    print(f"[flight-search] FAIL: empty + healthy control returned {out.get('status')}, expected empty")
    raise SystemExit(1)
print("[flight-search] OK: empty results are distinguished from a broken scraper")
PY
    :
  else
    echo "[flight-search] FAIL: failure-semantics check did not pass" >&2
    fail=1
  fi
fi

STORE="${FLIGHT_SEARCH_STORE:-${CHASSIS_HOME:-$HOME}/data/flight-search/tracked-routes.json}"
if [[ -d "$(dirname "$STORE")" ]]; then
  echo "[flight-search] OK: store directory exists ($(dirname "$STORE"))"
else
  echo "[flight-search] FAIL: store directory missing - run setup.sh" >&2
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  echo "[flight-search] validate failed." >&2
  exit 1
fi

echo "[flight-search] validate OK."
