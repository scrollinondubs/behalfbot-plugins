#!/usr/bin/env bash
# setup.sh - chef dependency setup.
#
# Idempotent: re-running is a no-op. Invoked by the chassis activate-plugins.sh
# on every bootstrap when modules.chef.enabled == true.
#
# Linux-first, no brew fallback.
#
# The interesting check here is the last one. This plugin reads a meal log it
# does not own, and the failure mode of a missing meal log is silence at 13:30
# on a Sunday with nothing in the logs to explain it. Better to say so now.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PSYCOPG_VERSION="3.2.3"

echo "[chef] checking deps..."

fail=0

if command -v python3 >/dev/null 2>&1; then
  echo "[chef] python3 present ($(python3 --version 2>&1))"
else
  echo "[chef] ERROR: python3 not found (Debian: apt-get install python3 python3-pip)." >&2
  fail=1
fi

pip_install() {
  # PEP 668 marks the system environment as externally managed on recent Debian
  # images, which rejects a plain install. The flag is the documented escape
  # hatch and correct inside a single-purpose container; the first attempt
  # covers hosts where the flag is not recognised.
  if pip3 install "$1" >/dev/null 2>&1; then
    return 0
  fi
  pip3 install --break-system-packages "$1" >/dev/null 2>&1
}

if [[ "$fail" -eq 0 ]]; then
  if python3 -c 'import psycopg' >/dev/null 2>&1; then
    echo "[chef] psycopg present"
  elif command -v pip3 >/dev/null 2>&1; then
    echo "[chef] installing psycopg[binary]==${PSYCOPG_VERSION}..."
    if pip_install "psycopg[binary]==${PSYCOPG_VERSION}"; then
      echo "[chef] psycopg installed"
    else
      echo "[chef] ERROR: pip install psycopg[binary]==${PSYCOPG_VERSION} failed." >&2
      fail=1
    fi
  else
    echo "[chef] ERROR: psycopg missing and pip3 unavailable." >&2
    fail=1
  fi
fi

TAXONOMY="${CHEF_TAXONOMY_PATH:-$SCRIPT_DIR/data/plant-taxonomy.json}"
if python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$TAXONOMY" >/dev/null 2>&1; then
  species=$(python3 -c "import json,sys; print(len(json.load(open(sys.argv[1])).get('plants',{})))" "$TAXONOMY")
  echo "[chef] taxonomy OK: $species canonical species"
else
  echo "[chef] ERROR: taxonomy at '$TAXONOMY' is missing or unparseable." >&2
  fail=1
fi

STATE_DIR="${CHEF_STATE_DIR:-${CHASSIS_HOME:-$HOME}/scheduled-tasks}"
if mkdir -p "$STATE_DIR" 2>/dev/null; then
  echo "[chef] state dir ready: $STATE_DIR"
else
  echo "[chef] ERROR: cannot create state dir '$STATE_DIR'. Without it the weekly" >&2
  echo "[chef]        dedup marker cannot persist and the report may run twice." >&2
  fail=1
fi

if [[ "${CHEF_OUTPUT_MODE:-file}" == "file" ]]; then
  OUT_DIR="${CHEF_OUTPUT_DIR:-${CHASSIS_HOME:-$HOME}/briefings/chef}"
  if mkdir -p "$OUT_DIR" 2>/dev/null; then
    echo "[chef] output dir ready: $OUT_DIR"
  else
    echo "[chef] ERROR: cannot create output dir '$OUT_DIR'." >&2
    fail=1
  fi
fi

# The data dependency. A WARN rather than an error: an install may enable chef
# before the meal log has accumulated anything, and that is a legitimate order
# to do it in. Silence with an explanation beats silence without one.
if [[ -n "${BEHALFBOT_PG_DSN:-${CHASSIS_PG_DSN:-}}" ]]; then
  echo "[chef] database DSN present in environment"
  if python3 - <<'PY' 2>/dev/null; then
import os, sys
try:
    import psycopg
except ImportError:
    sys.exit(1)
dsn = os.environ.get("BEHALFBOT_PG_DSN") or os.environ.get("CHASSIS_PG_DSN")
table = os.environ.get("CHEF_MEALS_TABLE", "bfl_meals")
try:
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass(%s)", (table,))
        sys.exit(0 if cur.fetchone()[0] else 1)
except Exception:
    sys.exit(1)
PY
    echo "[chef] meal log table reachable"
  else
    echo "[chef] WARN: could not confirm the meal log table exists. This plugin only" >&2
    echo "[chef]       READS a meal log written by the companion food-logging plugin." >&2
    echo "[chef]       Enable that plugin, or the weekly report will find nothing to" >&2
    echo "[chef]       count and stay silent." >&2
  fi
else
  echo "[chef] WARN: no BEHALFBOT_PG_DSN / CHASSIS_PG_DSN in the environment." >&2
  echo "[chef]       The analyzer cannot read the meal log without it." >&2
fi

if [[ "$fail" -ne 0 ]]; then
  echo "[chef] setup incomplete - see errors above." >&2
  exit 1
fi

echo "[chef] setup complete."
