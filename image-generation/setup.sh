#!/usr/bin/env bash
# setup.sh - image-generation dependency setup.
#
# Idempotent: re-running is a no-op. Invoked by the chassis activate-plugins.sh
# on every bootstrap when modules.image-generation.enabled == true.
#
# Linux-first, no brew fallback. Missing hard deps are a clear ERROR with manual
# instructions.
#
# Nothing here installs a backend. ComfyUI is roughly 20GB of model weights and
# a GPU-shaped decision, and the hosted API needs a key the operator has to
# provide. Both are checked and reported; neither is installed behind the
# operator's back.

set -euo pipefail

echo "[image-generation] checking deps..."

fail=0

for bin in curl jq; do
  if command -v "$bin" >/dev/null 2>&1; then
    echo "[image-generation] $bin present"
  else
    echo "[image-generation] ERROR: $bin not found. Install it via your platform's" >&2
    echo "[image-generation]        package manager (Debian: apt-get install $bin)." >&2
    fail=1
  fi
done

# Local backend: report reachability, never install. Absence is a WARN because
# the hosted backend still works.
COMFYUI_URL="${COMFYUI_URL:-http://localhost:8188}"
if command -v curl >/dev/null 2>&1 && curl -sf "$COMFYUI_URL/system_stats" >/dev/null 2>&1; then
  echo "[image-generation] ComfyUI reachable at $COMFYUI_URL"
  if [[ -z "${COMFYUI_OUTPUT_DIR:-}" ]]; then
    echo "[image-generation] WARN: ComfyUI is up but comfyui_output_dir is unset." >&2
    echo "[image-generation]       The local backend will refuse to run until it is set." >&2
  elif [[ ! -d "${COMFYUI_OUTPUT_DIR}" ]]; then
    echo "[image-generation] WARN: comfyui_output_dir '${COMFYUI_OUTPUT_DIR}' is not a" >&2
    echo "[image-generation]       readable directory from here." >&2
  else
    echo "[image-generation] ComfyUI output dir readable"
  fi
else
  echo "[image-generation] WARN: ComfyUI not reachable at $COMFYUI_URL." >&2
  echo "[image-generation]       The local backend will be unavailable. Install ComfyUI and" >&2
  echo "[image-generation]       its FLUX.1 weights, or use the hosted backend." >&2
fi

# Hosted backend: key presence only. Never printed, never written anywhere.
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  echo "[image-generation] hosted backend credential present in environment"
else
  echo "[image-generation] WARN: OPENAI_API_KEY not in the environment." >&2
  echo "[image-generation]       The hosted backend will be unavailable." >&2
fi

if [[ "$fail" -ne 0 ]]; then
  echo "[image-generation] setup incomplete - see errors above." >&2
  exit 1
fi

echo "[image-generation] setup complete."
