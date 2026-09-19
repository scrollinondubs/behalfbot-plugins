#!/usr/bin/env bash
# tts.sh - text to speech for the video-explainer plugin.
#
# Usage: tts.sh [--openai|--say] "text" output.mp3
#
# Engine selection, in order:
#   1. the --openai / --say flag, if given
#   2. $VIDEO_EXPLAINER_TTS  (openai | say)
#   3. openai when OPENAI_API_KEY is set, otherwise say
#
# If the host install already provides a text-to-speech script, point
# $VIDEO_EXPLAINER_TTS_BIN at it and that is used instead of this file.

set -euo pipefail

ENGINE="${VIDEO_EXPLAINER_TTS:-}"
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --openai) ENGINE="openai"; shift ;;
    --say|--local) ENGINE="say"; shift ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

TEXT="${1:?usage: tts.sh [--openai|--say] \"text\" output.mp3}"
OUT="${2:?usage: tts.sh [--openai|--say] \"text\" output.mp3}"

if [[ -z "$ENGINE" ]]; then
  if [[ -n "${OPENAI_API_KEY:-}" ]]; then ENGINE="openai"; else ENGINE="say"; fi
fi

case "$ENGINE" in
  say)
    command -v say >/dev/null || { echo "say not available; set OPENAI_API_KEY or install a TTS" >&2; exit 3; }
    AIFF="$(mktemp -t vxtts).aiff"
    trap 'rm -f "$AIFF"' EXIT
    say -v "${VIDEO_EXPLAINER_SAY_VOICE:-Daniel}" "$TEXT" -o "$AIFF"
    ffmpeg -y -loglevel error -i "$AIFF" -codec:a libmp3lame -q:a 4 "$OUT"
    ;;
  openai)
    : "${OPENAI_API_KEY:?OPENAI_API_KEY is not set}"
    PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({'model': sys.argv[1], 'input': sys.argv[2], 'voice': sys.argv[3], 'response_format': 'mp3'}))
" "${OPENAI_TTS_MODEL:-tts-1-hd}" "$TEXT" "${OPENAI_TTS_VOICE:-onyx}")
    curl -sf https://api.openai.com/v1/audio/speech \
      -H "Authorization: Bearer ${OPENAI_API_KEY}" \
      -H "Content-Type: application/json" \
      -d "$PAYLOAD" -o "$OUT"
    ;;
  *)
    echo "unknown engine: $ENGINE" >&2; exit 2 ;;
esac

echo "$OUT"
