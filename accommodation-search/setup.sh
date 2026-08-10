#!/usr/bin/env bash
# setup.sh - accommodation-search dependency setup.
#
# Idempotent: the second run is a no-op. It checks the installed upstream
# version against the pin in package.json and only reaches the network when
# they disagree.
#
# Linux-first (the chassis container is Debian slim). No brew fallback - a
# missing system dependency is a clear ERROR with manual instructions, never a
# platform-specific install attempt.
#
# The install is `npm ci` from the committed package-lock.json, deliberately.
# `npm ci` fails when the lockfile and package.json disagree; `npm install`
# quietly rewrites the lockfile. And there is no `npx -y` anywhere in this
# plugin: the version that runs on a customer machine is the one a human pinned
# and a lockfile hash covers, not whatever was published this morning.

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_PKG="$PLUGIN_DIR/node_modules/@openbnb/mcp-server-airbnb/package.json"
MIN_NODE_MAJOR=18

echo "[accommodation-search] checking deps..."

fail=0

if ! command -v node >/dev/null 2>&1; then
  echo "[accommodation-search] ERROR: node not found. Install Node.js ${MIN_NODE_MAJOR}+ via your" >&2
  echo "[accommodation-search]        platform's package manager (Debian: apt-get install nodejs npm)." >&2
  fail=1
else
  node_version="$(node --version 2>/dev/null || echo 'v0')"
  node_major="${node_version#v}"
  node_major="${node_major%%.*}"
  if [[ ! "$node_major" =~ ^[0-9]+$ ]] || (( node_major < MIN_NODE_MAJOR )); then
    echo "[accommodation-search] ERROR: node ${node_version} is too old. The upstream MCP server" >&2
    echo "[accommodation-search]        needs Node ${MIN_NODE_MAJOR}+." >&2
    fail=1
  else
    echo "[accommodation-search] node present (${node_version})"
  fi
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[accommodation-search] ERROR: npm not found. It ships with Node.js" >&2
  echo "[accommodation-search]        (Debian: apt-get install nodejs npm)." >&2
  fail=1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[accommodation-search] ERROR: python3 not found. It runs the MCP proxy that" >&2
  echo "[accommodation-search]        flags empty result sets (Debian: apt-get install python3)." >&2
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  echo "[accommodation-search] setup incomplete - see errors above." >&2
  exit 1
fi

read_json_field() {
  # $1 path to a JSON file, $2.. the key path. Prints the value or nothing.
  python3 -c '
import json, sys
try:
    node = json.load(open(sys.argv[1], encoding="utf-8"))
    for key in sys.argv[2:]:
        node = node[key]
    print(node)
except Exception:
    pass
' "$@"
}

pinned="$(read_json_field "$PLUGIN_DIR/package.json" dependencies @openbnb/mcp-server-airbnb)"
if [[ -z "$pinned" ]]; then
  echo "[accommodation-search] ERROR: no pinned @openbnb/mcp-server-airbnb version in package.json." >&2
  exit 1
fi

installed=""
if [[ -f "$UPSTREAM_PKG" ]]; then
  installed="$(read_json_field "$UPSTREAM_PKG" version)"
fi

if [[ "$installed" == "$pinned" ]]; then
  echo "[accommodation-search] @openbnb/mcp-server-airbnb@${pinned} already installed - nothing to do"
else
  if [[ -n "$installed" ]]; then
    echo "[accommodation-search] installed version ${installed} does not match pin ${pinned}, reinstalling"
  else
    echo "[accommodation-search] installing @openbnb/mcp-server-airbnb@${pinned} via npm ci..."
  fi
  (cd "$PLUGIN_DIR" && npm ci --omit=dev)
fi

if [[ ! -f "$UPSTREAM_PKG" ]]; then
  echo "[accommodation-search] ERROR: install finished but ${UPSTREAM_PKG} is missing." >&2
  exit 1
fi

echo "[accommodation-search] setup complete."
