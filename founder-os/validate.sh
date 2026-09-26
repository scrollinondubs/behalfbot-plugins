#!/usr/bin/env bash
# validate.sh - founder-os post-setup smoke check. Exit nonzero = degraded.
# No network calls. Checks the plugin layout and that the manifest parses.

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

for d in core contrib gates skills laya templates schema evals; do
  if [[ -d "$PLUGIN_DIR/$d" ]]; then
    echo "[founder-os] OK: $d/"
  else
    echo "[founder-os] FAIL: $d/ missing" >&2
    fail=1
  fi
done

if python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "$PLUGIN_DIR/openclaw.plugin.json"; then
  echo "[founder-os] OK: openclaw.plugin.json parses"
else
  echo "[founder-os] FAIL: openclaw.plugin.json is not valid JSON" >&2
  fail=1
fi

exit "$fail"
