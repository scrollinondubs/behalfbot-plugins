#!/usr/bin/env bash
# setup.sh - founder-os dependency setup.
#
# Idempotent: it only checks, it never installs, so re-running is always a
# no-op. Invoked by the chassis activate-plugins.sh on every bootstrap when
# modules.founder-os.enabled == true.
#
# Linux-first (the chassis container is Debian slim). No brew fallback - a
# missing dependency is an ERROR with manual instructions.

set -euo pipefail

echo "[founder-os] checking deps..."

if command -v python3 >/dev/null 2>&1; then
  echo "[founder-os] python3 present ($(python3 --version 2>&1))"
else
  echo "[founder-os] ERROR: python3 not found. Install it via your platform's" >&2
  echo "[founder-os]        package manager (Debian: apt-get install python3)." >&2
  exit 1
fi

# psycopg is a soft dependency: only the Postgres ledger backend needs it, and
# the chassis image already ships it. Never installed from here.
if python3 -c 'import psycopg' >/dev/null 2>&1; then
  echo "[founder-os] psycopg present ($(python3 -c 'import psycopg; print(psycopg.__version__)'))"
else
  echo "[founder-os] WARN: psycopg not importable. The Postgres ledger backend will not" >&2
  echo "[founder-os]       work; set ledger_backend: sqlite or install psycopg==3.2.3." >&2
fi

echo "[founder-os] setup complete."
