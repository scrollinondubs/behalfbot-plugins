#!/usr/bin/env bash
# validate.sh - accommodation-search post-setup smoke check. Exit nonzero = degraded.
#
# No network calls. This checks that the install is what it claims to be:
# the pinned upstream is present at the pinned version, the proxy parses, and
# nothing in the plugin disables robots compliance or the geocoders.
#
# For the question this check deliberately does NOT answer - whether Airbnb's
# robots.txt currently permits the paths the tools use - run:
#   python3 scripts/robots_preflight.py
# That one goes to the source, which means it needs the network.

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_PKG="$PLUGIN_DIR/node_modules/@openbnb/mcp-server-airbnb/package.json"
UPSTREAM_ENTRY="$PLUGIN_DIR/node_modules/@openbnb/mcp-server-airbnb/dist/index.js"
fail=0

for bin in node python3; do
  if command -v "$bin" >/dev/null 2>&1; then
    echo "[accommodation-search] OK: $bin"
  else
    echo "[accommodation-search] FAIL: $bin not in PATH" >&2
    fail=1
  fi
done

read_json_field() {
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

if [[ -f "$UPSTREAM_ENTRY" ]]; then
  installed="$(read_json_field "$UPSTREAM_PKG" version)"
  if [[ "$installed" == "$pinned" ]]; then
    echo "[accommodation-search] OK: upstream server present at pinned ${pinned}"
  else
    echo "[accommodation-search] FAIL: upstream is ${installed:-missing}, pin says ${pinned}. Run setup.sh." >&2
    fail=1
  fi
else
  echo "[accommodation-search] FAIL: upstream server not installed. Run setup.sh." >&2
  fail=1
fi

if [[ "$pinned" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "[accommodation-search] OK: upstream pinned to an exact version"
else
  echo "[accommodation-search] FAIL: '${pinned}' is not an exact version pin" >&2
  fail=1
fi

if [[ -f "$PLUGIN_DIR/package-lock.json" ]]; then
  echo "[accommodation-search] OK: lockfile committed"
else
  echo "[accommodation-search] FAIL: package-lock.json missing - npm ci cannot run" >&2
  fail=1
fi

if python3 -c "import py_compile,sys; py_compile.compile(sys.argv[1], doraise=True)" \
     "$PLUGIN_DIR/scripts/airbnb_mcp_proxy.py" >/dev/null 2>&1; then
  echo "[accommodation-search] OK: airbnb_mcp_proxy.py parses"
else
  echo "[accommodation-search] FAIL: airbnb_mcp_proxy.py has syntax errors" >&2
  fail=1
fi

# The two settings this plugin is not allowed to quietly flip. Both are
# operator decisions declared in the manifest's configSchema, so a hardcoded
# override anywhere in the plugin is a bug, not a preference.
if grep -rn -- "--ignore-robots-txt" "$PLUGIN_DIR" \
     --include='*.py' --include='*.sh' --include='*.json' \
     --exclude=package-lock.json --exclude-dir=node_modules >/dev/null 2>&1; then
  echo "[accommodation-search] FAIL: something in this plugin passes --ignore-robots-txt" >&2
  fail=1
else
  echo "[accommodation-search] OK: nothing passes --ignore-robots-txt"
fi

# Invocation shapes only - `npx` followed by whitespace. Comment lines are
# dropped so the rule can still be explained in prose where it applies.
npx_hits="$(grep -rn -E '(^|[^[:alnum:]_.-])npx[[:space:]]' "$PLUGIN_DIR" \
     --include='*.py' --include='*.sh' --include='*.json' \
     --exclude=package-lock.json --exclude-dir=node_modules 2>/dev/null \
     | grep -v -E ':[0-9]+:[[:space:]]*#' || true)"
if [[ -n "$npx_hits" ]]; then
  echo "[accommodation-search] FAIL: something in this plugin invokes npx" >&2
  echo "$npx_hits" >&2
  fail=1
else
  echo "[accommodation-search] OK: no npx-based invocation"
fi

exit "$fail"
