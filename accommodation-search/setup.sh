#!/usr/bin/env bash
# setup.sh - accommodation-search dependency setup.
#
# There are no third-party dependencies to install. See requirements.txt for
# why that is the pin rather than a gap. So this script checks that the
# interpreter is new enough, that nothing in the plugin has grown an import
# outside the standard library, and that the directory the call ledger lives in
# exists and is writable.
#
# Idempotent by construction: it installs nothing, so a second run does the
# same checks and reaches the same end state.
#
# Linux-first. The chassis container is Debian slim, so a missing dependency is
# an ERROR with the apt command to fix it, never a brew attempt.

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIN_PYTHON_MINOR=9

cat >&2 <<'DORMANT'
[accommodation-search] ============================================================
[accommodation-search] DORMANT PLUGIN - THE SUPPLIER NO LONGER EXISTS
[accommodation-search]
[accommodation-search] Amadeus decommissioned its Self-Service portal on 17 July
[accommodation-search] 2026. Registration was paused before that and existing keys
[accommodation-search] were disabled on the day. No credentials can be obtained, so
[accommodation-search] every tool call in this plugin will fail authentication.
[accommodation-search]
[accommodation-search] Setup still runs and still passes - there is nothing to
[accommodation-search] install and the checks below are honest. That is not an
[accommodation-search] endorsement. Do not enable this plugin.
[accommodation-search]
[accommodation-search] It is kept for its supplier-neutral tool interface, which a
[accommodation-search] replacement supplier slots into without changing callers.
[accommodation-search] ============================================================
DORMANT

echo "[accommodation-search] checking deps..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "[accommodation-search] ERROR: python3 not found. Everything in this plugin is" >&2
  echo "[accommodation-search]        Python (Debian: apt-get install python3)." >&2
  exit 1
fi

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, ${MIN_PYTHON_MINOR}) else 1)"; then
  echo "[accommodation-search] ERROR: python3 3.${MIN_PYTHON_MINOR}+ is required." >&2
  echo "[accommodation-search]        Found: $(python3 --version 2>&1)" >&2
  exit 1
fi
echo "[accommodation-search] python3 present ($(python3 --version 2>&1))"

# The import audit. Not a formality: the one dependency rule this plugin has is
# that it has none, and an import added in a hurry is exactly how that stops
# being true without anybody deciding it should.
if ! python3 "$PLUGIN_DIR/scripts/check_stdlib_only.py" "$PLUGIN_DIR"; then
  echo "[accommodation-search] ERROR: the import audit failed - see above." >&2
  exit 1
fi

STATE_DIR="${ACCOMMODATION_STATE_DIR:-$PLUGIN_DIR/var}"
if mkdir -p "$STATE_DIR" 2>/dev/null && [ -w "$STATE_DIR" ]; then
  echo "[accommodation-search] call ledger directory ready: $STATE_DIR"
else
  # Soft: an unwritable state directory costs the running count of supplier
  # calls, which is worth a warning and is not worth failing an install over.
  echo "[accommodation-search] WARN: $STATE_DIR is not writable. Supplier calls will" >&2
  echo "[accommodation-search]       not be counted; set ACCOMMODATION_STATE_DIR to a" >&2
  echo "[accommodation-search]       writable path to restore the monthly ledger." >&2
fi

if [ -n "${AMADEUS_CLIENT_ID:-}" ] && [ -n "${AMADEUS_CLIENT_SECRET:-}" ]; then
  echo "[accommodation-search] Amadeus credentials present in the environment"
else
  # Soft on purpose. The plugin installs, validates and demos with no account
  # at all through its committed fixtures; credentials are what turns it live.
  echo "[accommodation-search] WARN: AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET are not"
  echo "[accommodation-search]       both set, so live search will refuse. Register free at"
  echo "[accommodation-search]       developers.amadeus.com and export them. The offline"
  echo "[accommodation-search]       demo path works without them:"
  echo "[accommodation-search]       python3 scripts/demo.py --fixtures happy --city LON"
fi

echo "[accommodation-search] setup complete."
