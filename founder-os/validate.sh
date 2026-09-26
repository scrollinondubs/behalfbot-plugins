#!/usr/bin/env bash
# validate.sh - founder-os post-setup smoke check. Exit nonzero = degraded.
# No network calls. Checks the plugin layout, that the manifest parses, and
# that the content (and the template examples) pass scripts/lint_content.py.

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

for root in "$PLUGIN_DIR" "$PLUGIN_DIR/templates/examples"; do
  if python3 "$PLUGIN_DIR/scripts/lint_content.py" --root "$root"; then
    echo "[founder-os] OK: content lint ($root)"
  else
    echo "[founder-os] FAIL: content lint ($root)" >&2
    fail=1
  fi
done

exit "$fail"
