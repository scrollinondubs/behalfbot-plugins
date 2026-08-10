#!/usr/bin/env bash
# setup.sh - flight-search dependency setup.
#
# Idempotent: re-running is a no-op once the pinned dependency set is present.
# Invoked by the chassis activate-plugins.sh on every bootstrap when
# modules.flight-search.enabled == true.
#
# Linux-first (the chassis container is Debian slim). No brew fallback - on a
# host with no supported package path, a missing dependency is an ERROR with
# manual instructions, never a platform-specific install attempt.
#
# Everything installed here comes from requirements.lock.txt, which pins the
# full transitive closure to exact versions. Nothing resolves at install time.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCKFILE="$SCRIPT_DIR/requirements.lock.txt"
PINNED_VERSION="$(grep -E '^flights==' "$SCRIPT_DIR/requirements.txt" | head -1 | cut -d= -f3)"

echo "[flight-search] checking deps..."

fail=0

if command -v python3 >/dev/null 2>&1; then
  echo "[flight-search] python3 present ($(python3 --version 2>&1))"
else
  echo "[flight-search] ERROR: python3 not found. Install it via your platform's" >&2
  echo "[flight-search]        package manager (Debian: apt-get install python3 python3-pip)." >&2
  fail=1
fi

if [[ "$fail" -eq 0 ]] && ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "[flight-search] ERROR: python3 is older than 3.10, which the pinned flights release requires." >&2
  fail=1
fi

pip_install() {
  # PEP 668 marks the system environment as externally managed on recent Debian
  # images, which rejects a plain install. The flag is the documented escape
  # hatch and correct inside a single-purpose container; the first attempt
  # covers hosts where the flag is not recognised.
  if pip3 install "$@" >/dev/null 2>&1; then
    return 0
  fi
  pip3 install --break-system-packages "$@" >/dev/null 2>&1
}

# The idempotency check is the exact pinned version, not merely "is it
# importable". A leftover older flights from another install would otherwise
# satisfy a bare import check and leave the install running unpinned code.
installed_version() {
  python3 - <<'PY' 2>/dev/null || true
try:
    from importlib import metadata
    print(metadata.version("flights"))
except Exception:
    print("")
PY
}

if [[ "$fail" -eq 0 ]]; then
  if [[ ! -f "$LOCKFILE" ]]; then
    echo "[flight-search] ERROR: $LOCKFILE is missing - refusing to install unpinned." >&2
    fail=1
  fi
fi

if [[ "$fail" -eq 0 ]]; then
  CURRENT="$(installed_version)"
  if [[ "$CURRENT" == "$PINNED_VERSION" ]]; then
    echo "[flight-search] flights==$PINNED_VERSION already installed"
  elif command -v pip3 >/dev/null 2>&1; then
    if [[ -n "$CURRENT" ]]; then
      echo "[flight-search] flights $CURRENT installed, pin is $PINNED_VERSION - reinstalling from the lockfile"
    else
      echo "[flight-search] installing the pinned dependency set from requirements.lock.txt..."
    fi
    if pip_install -r "$LOCKFILE"; then
      AFTER="$(installed_version)"
      if [[ "$AFTER" == "$PINNED_VERSION" ]]; then
        echo "[flight-search] flights==$PINNED_VERSION installed"
      else
        echo "[flight-search] ERROR: after install, flights reports '$AFTER', expected '$PINNED_VERSION'." >&2
        fail=1
      fi
    else
      echo "[flight-search] ERROR: pip install -r $LOCKFILE failed." >&2
      echo "[flight-search]        Retry manually to see why: pip3 install -r $LOCKFILE" >&2
      fail=1
    fi
  else
    echo "[flight-search] ERROR: flights missing and pip3 unavailable to install it." >&2
    echo "[flight-search]        Install pip first (Debian: apt-get install python3-pip), then:" >&2
    echo "[flight-search]        pip3 install -r $LOCKFILE" >&2
    fail=1
  fi
fi

# Both directories must exist before the first check runs, and both must be on
# storage that survives a container rebuild - a tracked route that dies with the
# container is not a tracked route.
STORE="${FLIGHT_SEARCH_STORE:-${CHASSIS_HOME:-$HOME}/data/flight-search/tracked-routes.json}"
STATE_DIR="${FLIGHT_SEARCH_STATE_DIR:-${CHASSIS_HOME:-$HOME}/scheduled-tasks}"

for dir in "$(dirname "$STORE")" "$STATE_DIR"; do
  if mkdir -p "$dir" 2>/dev/null; then
    echo "[flight-search] directory ready: $dir"
  else
    echo "[flight-search] ERROR: cannot create '$dir'." >&2
    fail=1
  fi
done

if [[ "$fail" -ne 0 ]]; then
  echo "[flight-search] setup incomplete - see errors above." >&2
  exit 1
fi

echo "[flight-search] setup complete."
