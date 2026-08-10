#!/usr/bin/env bash
# setup.sh - restaurant-booking dependency setup.
#
# Idempotent: re-running is a no-op when deps are already present. Invoked by
# the chassis activate-plugins.sh on every bootstrap when
# modules.restaurant-booking.enabled == true.
#
# Linux-first (the chassis container is Debian slim). No brew fallback - on a
# host without a supported package path, a missing dep is an ERROR with manual
# instructions, not a platform-specific install attempt.
#
# Pinning: playwright is pinned to an exact version in package.json with
# package-lock.json committed, and installed with `npm ci` rather than
# `npm install`. `npm ci` fails when the lockfile and the manifest disagree;
# `npm install` quietly rewrites the lockfile. The browser download is driven
# by the local playwright binary, never `npx -y`.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[restaurant-booking] checking deps..."

fail=0

if command -v python3 >/dev/null 2>&1; then
  echo "[restaurant-booking] python3 present ($(python3 --version 2>&1))"
else
  echo "[restaurant-booking] ERROR: python3 not found (Debian: apt-get install python3)." >&2
  fail=1
fi

if command -v node >/dev/null 2>&1; then
  echo "[restaurant-booking] node present ($(node --version 2>/dev/null))"
else
  echo "[restaurant-booking] ERROR: node not found. Install Node.js via your platform's" >&2
  echo "[restaurant-booking]        package manager (Debian: apt-get install nodejs npm)." >&2
  fail=1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[restaurant-booking] ERROR: npm not found; cannot install the playwright dependency." >&2
  fail=1
fi

# node_modules from the committed lockfile. `npm ci` is already idempotent: it
# is a clean install from package-lock.json every time and never mutates the
# lockfile. Skipped when the tree already matches, so a warm bootstrap is fast.
if [[ "$fail" -eq 0 ]]; then
  if node -e "require.resolve('playwright/package.json', { paths: ['$SCRIPT_DIR'] })" >/dev/null 2>&1 \
     && [[ "$(node -e "console.log(require('$SCRIPT_DIR/node_modules/playwright/package.json').version)" 2>/dev/null)" \
           == "$(node -e "console.log(require('$SCRIPT_DIR/package.json').dependencies.playwright)" 2>/dev/null)" ]]; then
    echo "[restaurant-booking] playwright already at the pinned version"
  else
    echo "[restaurant-booking] installing node deps from the lockfile (npm ci)..."
    if ! (cd "$SCRIPT_DIR" && npm ci --no-audit --no-fund); then
      echo "[restaurant-booking] ERROR: npm ci failed. If it reports a lockfile mismatch," >&2
      echo "[restaurant-booking]        that is the pin doing its job - do not run npm install" >&2
      echo "[restaurant-booking]        to 'fix' it. Regenerate the lockfile deliberately." >&2
      fail=1
    fi
  fi
fi

# Chromium. The FULL browser build, not the headless shell: the shell
# advertises HeadlessChrome in its user agent and TheFork refuses it outright.
# `playwright install` is idempotent by design - it is a no-op once the browser
# revision for this playwright version is in the cache.
if [[ "$fail" -eq 0 ]]; then
  PW_BIN="$SCRIPT_DIR/node_modules/.bin/playwright"
  if [[ -x "$PW_BIN" ]]; then
    echo "[restaurant-booking] ensuring chromium is installed..."
    if ! (cd "$SCRIPT_DIR" && "$PW_BIN" install chromium); then
      echo "[restaurant-booking] ERROR: playwright install chromium failed." >&2
      echo "[restaurant-booking]        On Debian you may also need the browser's system" >&2
      echo "[restaurant-booking]        libraries: $PW_BIN install-deps chromium" >&2
      fail=1
    fi
  else
    echo "[restaurant-booking] ERROR: local playwright binary missing at $PW_BIN." >&2
    fail=1
  fi
fi

# Soft dependency: without the Vaultwarden item the plugin cannot log in, but an
# install may legitimately enable the module before the operator has added it.
VW_ITEM="${RESTAURANT_BOOKING_VW_ITEM:-thefork-credentials}"
BW_FETCH="${CHASSIS_HOME:-$HOME}/scripts/bw-fetch.sh"
if [[ -x "$BW_FETCH" || -f "$BW_FETCH" ]]; then
  echo "[restaurant-booking] credential fetcher present at $BW_FETCH"
  echo "[restaurant-booking] NOTE: credentials for '$VW_ITEM' are read at booking time"
  echo "[restaurant-booking]       and never written to .env or to disk. Not checked here" >&2
  echo "[restaurant-booking]       because that would unlock the vault during bootstrap." >&2
else
  echo "[restaurant-booking] WARN: no bw-fetch.sh at $BW_FETCH. TheFork login needs it;" >&2
  echo "[restaurant-booking]       set CHASSIS_HOME or install the chassis credential helper." >&2
fi

if [[ "$fail" -ne 0 ]]; then
  echo "[restaurant-booking] setup incomplete - see errors above." >&2
  exit 1
fi

echo "[restaurant-booking] setup complete."
