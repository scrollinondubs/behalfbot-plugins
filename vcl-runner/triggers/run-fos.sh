#!/usr/bin/env bash
# run-fos.sh
# "run fos": run the VCL runner's tick now, instead of waiting for the
# heartbeat. The dispatcher ticks every 15 minutes by default, so work queued
# in the Hub on "My BehalfBot" can sit that long. This is the same tick, run
# once, on the install it is called on, with that install's own agent key.
#
# Called two ways: by the run-fos skill from the owner's chat session, and by
# the chassis trigger dispatcher (contracts.triggers in the manifest). Either
# way it prints one plain line for the owner and exits 0. It never prints the
# agent key: the gather script reads it from the install's .env itself.
#
# A tick running at the same time as the heartbeat is safe. The Hub leases
# each job to one claimer, so a job is never worked twice.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
HOME_DIR="${CUSTOMER_HOME:-${CHASSIS_HOME:-}}"

flag_on() {
  # $1 flag file under scheduled-tasks/. True when it says "enabled": true.
  # A flag that cannot be read counts as on: a stop control fails closed.
  local f="$HOME_DIR/scheduled-tasks/$1"
  [ -n "$HOME_DIR" ] && [ -f "$f" ] || return 1
  python3 - "$f" <<'PY'
import json, sys
try:
    on = json.load(open(sys.argv[1], encoding="utf-8")).get("enabled") is True
except Exception:
    on = True
sys.exit(0 if on else 1)
PY
}

if flag_on halt.json; then
  echo "Not run: this BehalfBot is halted. Your queued jobs wait in the Hub until the halt is lifted."
  exit 0
fi
if flag_on conservation-mode.json; then
  echo "Not run: this BehalfBot is in conservation mode. Your queued jobs wait in the Hub until it is lifted."
  exit 0
fi

OUTPUT="$(bash "$PLUGIN_ROOT/scripts/gather-vcl-runner.sh")"

SUMMARY="$OUTPUT" python3 - <<'PY'
import json, os

try:
    s = json.loads(os.environ.get("SUMMARY", "").strip().splitlines()[-1])
except Exception:
    print("The runner gave no readable answer. Check the heartbeat log.")
    raise SystemExit(0)

reason = str(s.get("reason") or "").strip()
jobs = int(s.get("jobs") or 0)
if int(s.get("count") or 0) > 0:
    print(f"The runner needs you: {reason or 'it stopped without saying why'}.")
elif "not configured" in reason:
    print("The runner has no agent key yet. Run vcl-runner setup with the key from the Hub settings.")
elif jobs == 0:
    quiet = not reason or reason == "nothing queued"
    print("Nothing queued in the Hub." if quiet else f"Nothing ran: {reason}.")
else:
    parts = [f"{int(s.get('posted') or 0)} posted back to the Hub"]
    if s.get("dropped"):
        parts.append(f"{int(s['dropped'])} dropped (the Hub had moved on)")
    if s.get("failed_steps"):
        parts.append(f"{int(s['failed_steps'])} with a failed step (the Hub shows Retry)")
    line = f"Ran {jobs} job{'' if jobs == 1 else 's'}: {', '.join(parts)}."
    # "queue drained" is the ordinary end of a tick; anything else is worth passing on.
    print(line if reason in ("", "queue drained") else f"{line} Then it stopped: {reason}.")
PY
