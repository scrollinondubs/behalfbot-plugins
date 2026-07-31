#!/usr/bin/env bash
# validate.sh - chef post-setup smoke check. Exit nonzero = degraded.
#
# No network and no database. The analyzer's mapping layer is pure and takes
# rows as an argument, so the part most worth testing - does a free-text meal
# string resolve to the right species, and does salmon stay unflagged - can be
# checked offline against synthetic rows.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

if python3 -m py_compile "$SCRIPT_DIR/scripts/chef_plant_count.py" >/dev/null 2>&1; then
  echo "[chef] OK: chef_plant_count.py compiles"
else
  echo "[chef] FAIL: chef_plant_count.py has syntax errors" >&2
  fail=1
fi

if bash -n "$SCRIPT_DIR/scripts/gather-chef-weekly.sh"; then
  echo "[chef] OK: gather-chef-weekly.sh parses"
else
  echo "[chef] FAIL: gather-chef-weekly.sh has syntax errors" >&2
  fail=1
fi

if [[ "$fail" -eq 0 ]]; then
  if CHEF_PLUGIN_DIR="$SCRIPT_DIR" python3 - "$SCRIPT_DIR" <<'PY'; then
import sys, pathlib
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts"))
from chef_plant_count import PlantMapper, analyze  # noqa: E402

mapper = PlantMapper()

# Mapping: a hand-typed fragment with an adjective must still resolve, and a
# composite catch-all that names no species must NOT resolve. Counting "mixed
# vegetables" as one plant is the specific inflation this taxonomy was corrected
# to remove.
assert mapper.resolve_plant("sliced red onion") is not None, "adjective form did not resolve"
assert mapper.resolve_plant("mixed vegetables") is None, "composite catch-all resolved as a plant"

# Mercury gating: low-mercury species never flag. This is a hard refusal in the
# skill, so it is worth a test rather than a comment.
assert mapper.mercury_flag("grilled salmon") is None, "salmon flagged as high-mercury"

rows = [
    {"date": "2026-01-01", "description": "kale and chickpeas with brown rice", "vision_items_json": None},
    {"date": "2026-01-02", "description": "salmon, broccoli", "vision_items_json": None},
]
result = analyze(rows, mapper)
assert result["days_logged"] == 2, f"expected 2 logged days, got {result['days_logged']}"
assert result["distinct_plant_count"] >= 3, f"expected 3+ plants, got {result['distinct_plant_count']}"
assert result["target"] >= 5, "plant target looks unset"
assert not any(f["fish"] for f in result["high_mercury_fish"]), "salmon produced a mercury entry"
print("analyzer self-check passed")
PY
    echo "[chef] OK: analyzer mapping and mercury gating"
  else
    echo "[chef] FAIL: analyzer self-check failed" >&2
    fail=1
  fi
fi

STATE_DIR="${CHEF_STATE_DIR:-${CHASSIS_HOME:-$HOME}/scheduled-tasks}"
if [[ -d "$STATE_DIR" && -w "$STATE_DIR" ]]; then
  echo "[chef] OK: state dir writable ($STATE_DIR)"
else
  echo "[chef] FAIL: state dir '$STATE_DIR' missing or not writable - the weekly" >&2
  echo "[chef]       dedup marker cannot persist" >&2
  fail=1
fi

exit "$fail"
