#!/usr/bin/env bash
# validate.sh - post-setup smoke check. Nonzero means degraded, not fatal.
#
# Renders one slide and muxes it against a generated silent track, which
# exercises the whole pipeline except the narration engine. It deliberately
# does not call text to speech: that costs money on the hosted engine and a
# smoke test should never bill anybody.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${SCRIPT_DIR}/skills/video-explainer"
FAIL=0

log()  { echo "[video-explainer] $1"; }
warn() { echo "[video-explainer] WARN: $1" >&2; FAIL=1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

for bin in ffmpeg ffprobe python3; do
  command -v "$bin" >/dev/null 2>&1 || { warn "$bin missing"; }
done

if ! python3 -c "import PIL" >/dev/null 2>&1; then
  warn "Pillow missing, the bundled slide renderer will not run"
else
  if python3 - "$SKILL_DIR" "$WORK/slide.png" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from slidekit import Slide, render
render(Slide(title="Smoke test", kicker="validate", lines=[("Rendered locally.", "muted")]), sys.argv[2])
PY
  then
    log "slide renderer ok"
  else
    warn "slide renderer failed"
  fi
fi

if command -v ffmpeg >/dev/null 2>&1 && [[ -f "$WORK/slide.png" ]]; then
  if ffmpeg -y -loglevel error \
      -loop 1 -framerate 30 -i "$WORK/slide.png" \
      -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 \
      -t 1 -c:v libx264 -tune stillimage -pix_fmt yuv420p \
      -c:a aac -movflags +faststart "$WORK/out.mp4" >/dev/null 2>&1; then
    log "encode ok ($(ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 "$WORK/out.mp4")s)"
  else
    warn "ffmpeg could not encode h264 + aac. Check your build's encoders."
  fi
fi

if [[ -d "${SCRIPT_DIR}/remotion-template/node_modules" ]]; then
  log "animated path installed"
else
  log "animated path not installed (slide path works without it)"
fi

if [[ $FAIL -eq 0 ]]; then
  log "validate ok"
else
  log "validate finished degraded, see warnings above"
fi
exit $FAIL
