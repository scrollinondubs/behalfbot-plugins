#!/usr/bin/env bash
# validate.sh - image-generation post-setup smoke check. Exit nonzero = degraded.
#
# Generating an image to prove the plugin works would cost either money or ten
# minutes, so this checks everything short of that: tools, script syntax,
# workflow graph shape, and whether at least one backend is actually usable.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

for bin in curl jq; do
  if command -v "$bin" >/dev/null 2>&1; then
    echo "[image-generation] OK: $bin"
  else
    echo "[image-generation] FAIL: $bin not in PATH" >&2
    fail=1
  fi
done

if bash -n "$SCRIPT_DIR/scripts/generate-image.sh"; then
  echo "[image-generation] OK: generate-image.sh parses"
else
  echo "[image-generation] FAIL: generate-image.sh has syntax errors" >&2
  fail=1
fi

WORKFLOW="${COMFYUI_WORKFLOW_PATH:-$SCRIPT_DIR/config/comfyui-flux-workflow.json}"
if command -v jq >/dev/null 2>&1; then
  if jq -e . "$WORKFLOW" >/dev/null 2>&1; then
    echo "[image-generation] OK: workflow JSON parses"
    for node_var in COMFYUI_PROMPT_NODE:6 COMFYUI_SEED_NODE:25 COMFYUI_OUTPUT_NODE:9; do
      var="${node_var%%:*}"
      default="${node_var##*:}"
      node="${!var:-$default}"
      if jq -e --arg n "$node" 'has($n)' "$WORKFLOW" >/dev/null 2>&1; then
        echo "[image-generation] OK: workflow has node $node ($var)"
      else
        echo "[image-generation] FAIL: workflow has no node '$node' for $var" >&2
        fail=1
      fi
    done
  else
    echo "[image-generation] FAIL: workflow JSON at $WORKFLOW is missing or unparseable" >&2
    fail=1
  fi
fi

# At least one usable backend. Neither present is a degraded install: the plugin
# is enabled but cannot produce an image.
backends=0
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  echo "[image-generation] OK: hosted backend credential present"
  backends=$((backends + 1))
fi
if curl -sf "${COMFYUI_URL:-http://localhost:8188}/system_stats" >/dev/null 2>&1 \
   && [[ -n "${COMFYUI_OUTPUT_DIR:-}" ]]; then
  echo "[image-generation] OK: local ComfyUI backend reachable and configured"
  backends=$((backends + 1))
fi
if [[ "$backends" -eq 0 ]]; then
  echo "[image-generation] FAIL: no usable backend - ComfyUI unreachable or" >&2
  echo "[image-generation]       unconfigured, and no hosted credential in the environment." >&2
  fail=1
fi

exit "$fail"
