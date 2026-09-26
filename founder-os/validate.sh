#!/usr/bin/env bash
# validate.sh - founder-os post-setup smoke check. Exit nonzero = degraded.
# No network calls. Checks the plugin layout, that the manifest parses, and
# that the content (and the template examples) pass scripts/lint_content.py,
# and that the ledger migrations apply to an in-memory SQLite database.

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

if python3 "$PLUGIN_DIR/scripts/run_evals.py" validate; then
  echo "[founder-os] OK: eval fixtures"
else
  echo "[founder-os] FAIL: eval fixtures" >&2
  fail=1
fi

# Applies every migration to a throwaway in-memory SQLite database. Proves the
# schema files parse and the storage interface imports, without touching the
# real ledger.
if python3 - "$PLUGIN_DIR" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from founder_ledger import SqliteLedger
with SqliteLedger(":memory:") as ledger:
    applied = ledger.run_migrations()
print(f"[founder-os] ledger migrations apply cleanly: {', '.join(applied)}")
PY
then
  echo "[founder-os] OK: ledger schema"
else
  echo "[founder-os] FAIL: ledger schema or storage interface is broken" >&2
  fail=1
fi

exit "$fail"
