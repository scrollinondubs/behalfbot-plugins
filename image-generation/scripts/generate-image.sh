#!/usr/bin/env bash
# generate-image.sh - generate an image from a text prompt.
#
# Usage: generate-image.sh [--comfyui|--openai] "prompt" [output_path]
#
# Backends:
#   --comfyui   local ComfyUI running a FLUX.1 graph. Free, private, minutes.
#   --openai    hosted image API. Paid, seconds, better at text in the image.
#
# With no flag the backend comes from IMAGEGEN_DEFAULT_BACKEND (default: comfyui).
#
# Every knob is an env var set from the plugin's configSchema. Credentials are
# read from the process environment only - this script never sources a .env or
# reads a secret off disk, because a plugin that quietly opens a credential file
# it did not declare is exactly the failure mode this repo is shaped to avoid.

set -euo pipefail

BACKEND="${IMAGEGEN_DEFAULT_BACKEND:-comfyui}"

case "${1:-}" in
  --openai)  BACKEND="openai";  shift ;;
  --comfyui) BACKEND="comfyui"; shift ;;
esac

PROMPT="${1:-}"
if [[ -z "$PROMPT" ]]; then
  echo "Usage: generate-image.sh [--comfyui|--openai] \"prompt\" [output_path]" >&2
  exit 2
fi

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_DIR="${IMAGEGEN_OUTPUT_DIR:-${CHASSIS_HOME:-$HOME}/temp}"
OUTPUT="${2:-$OUTPUT_DIR/generated-${TIMESTAMP}.png}"

mkdir -p "$(dirname "$OUTPUT")"

for bin in curl jq; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "Error: $bin is required but not in PATH" >&2
    exit 1
  fi
done

# --- Hosted backend -------------------------------------------------------
if [[ "$BACKEND" == "openai" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "Error: OPENAI_API_KEY is not set in the environment." >&2
    echo "       Put it in the chassis secret store; this script does not read files." >&2
    exit 1
  fi

  BASE_URL="${IMAGEGEN_OPENAI_BASE_URL:-https://api.openai.com/v1}"
  MODEL="${IMAGEGEN_OPENAI_MODEL:-gpt-image-1}"
  SIZE="${IMAGEGEN_OPENAI_SIZE:-1024x1024}"
  QUALITY="${IMAGEGEN_OPENAI_QUALITY:-high}"

  echo "Generating image ($MODEL): $PROMPT" >&2
  echo "Output: $OUTPUT" >&2

  REQUEST=$(jq -n \
    --arg prompt "$PROMPT" \
    --arg model "$MODEL" \
    --arg size "$SIZE" \
    --arg quality "$QUALITY" \
    '{model: $model, prompt: $prompt, size: $size, quality: $quality, n: 1}')

  RESPONSE=$(curl -sf "$BASE_URL/images/generations" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $OPENAI_API_KEY" \
    -d "$REQUEST" 2>/dev/null || true)

  if [[ -z "$RESPONSE" ]]; then
    echo "Error: no response from $BASE_URL/images/generations" >&2
    exit 1
  fi

  # Some models return base64 inline, others a signed URL. Handle both.
  B64=$(printf '%s' "$RESPONSE" | jq -r '.data[0].b64_json // empty' 2>/dev/null || true)
  if [[ -n "$B64" ]]; then
    printf '%s' "$B64" | base64 -d > "$OUTPUT"
  else
    IMG_URL=$(printf '%s' "$RESPONSE" | jq -r '.data[0].url // empty' 2>/dev/null || true)
    if [[ -n "$IMG_URL" ]]; then
      curl -sf "$IMG_URL" -o "$OUTPUT"
    else
      echo "Error: no image data in the response" >&2
      printf '%s' "$RESPONSE" | jq '.error // .' >&2
      exit 1
    fi
  fi

  if [[ -s "$OUTPUT" ]]; then
    echo "$OUTPUT"
    exit 0
  fi
  echo "Error: output file is empty" >&2
  exit 1
fi

# --- Local ComfyUI backend ------------------------------------------------
COMFYUI_URL="${COMFYUI_URL:-http://localhost:8188}"
COMFYUI_OUTPUT_DIR="${COMFYUI_OUTPUT_DIR:-}"
WORKFLOW="${COMFYUI_WORKFLOW_PATH:-}"
PROMPT_NODE="${COMFYUI_PROMPT_NODE:-6}"
SEED_NODE="${COMFYUI_SEED_NODE:-25}"
OUTPUT_NODE="${COMFYUI_OUTPUT_NODE:-9}"
TIMEOUT="${COMFYUI_TIMEOUT_SECONDS:-900}"

if [[ -z "$COMFYUI_OUTPUT_DIR" ]]; then
  echo "Error: COMFYUI_OUTPUT_DIR is not set." >&2
  echo "       Set modules.image-generation.comfyui_output_dir to ComfyUI's own" >&2
  echo "       output directory - the path depends on where ComfyUI was installed," >&2
  echo "       so there is deliberately no default to guess at." >&2
  exit 1
fi

if [[ -z "$WORKFLOW" || ! -f "$WORKFLOW" ]]; then
  echo "Error: workflow JSON not found at '${WORKFLOW:-<unset>}'." >&2
  echo "       Set COMFYUI_WORKFLOW_PATH, or enable the plugin so its env contract" >&2
  echo "       points at the shipped config/comfyui-flux-workflow.json." >&2
  exit 1
fi

if ! curl -sf "$COMFYUI_URL/system_stats" >/dev/null 2>&1; then
  echo "Error: ComfyUI is not reachable at $COMFYUI_URL" >&2
  exit 1
fi

SEED=$((RANDOM * RANDOM))
WORKFLOW_JSON=$(jq \
  --arg prompt "$PROMPT" \
  --argjson seed "$SEED" \
  --arg pnode "$PROMPT_NODE" \
  --arg snode "$SEED_NODE" \
  '.[$pnode].inputs.text = $prompt | .[$snode].inputs.noise_seed = $seed' \
  "$WORKFLOW")

echo "Generating image (ComfyUI): $PROMPT" >&2
echo "Output: $OUTPUT" >&2

RESPONSE=$(curl -sf "$COMFYUI_URL/prompt" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --argjson wf "$WORKFLOW_JSON" '{prompt: $wf}')" 2>/dev/null || true)

PROMPT_ID=$(printf '%s' "$RESPONSE" | jq -r '.prompt_id // empty' 2>/dev/null || true)
if [[ -z "$PROMPT_ID" ]]; then
  echo "Error: failed to submit workflow" >&2
  echo "Response: $RESPONSE" >&2
  exit 1
fi

echo "Submitted job: $PROMPT_ID" >&2

ELAPSED=0
while [[ $ELAPSED -lt $TIMEOUT ]]; do
  HISTORY=$(curl -sf "$COMFYUI_URL/history/$PROMPT_ID" 2>/dev/null || true)

  HAS_RESULT=$(printf '%s' "$HISTORY" | jq -r --arg id "$PROMPT_ID" '.[$id] // empty' 2>/dev/null || true)
  if [[ -n "$HAS_RESULT" ]]; then
    STATUS=$(printf '%s' "$HISTORY" | jq -r --arg id "$PROMPT_ID" '.[$id].status.status_str // empty' 2>/dev/null || true)
    if [[ "$STATUS" == "error" ]]; then
      echo "Error: generation failed" >&2
      printf '%s' "$HISTORY" | jq --arg id "$PROMPT_ID" '.[$id].status' >&2
      exit 1
    fi

    FILENAME=$(printf '%s' "$HISTORY" \
      | jq -r --arg id "$PROMPT_ID" --arg out "$OUTPUT_NODE" \
        '.[$id].outputs[$out].images[0].filename // empty' 2>/dev/null || true)
    if [[ -n "$FILENAME" ]]; then
      if [[ ! -f "$COMFYUI_OUTPUT_DIR/$FILENAME" ]]; then
        echo "Error: ComfyUI reported '$FILENAME' but it is not readable at" >&2
        echo "       $COMFYUI_OUTPUT_DIR/$FILENAME - check comfyui_output_dir." >&2
        exit 1
      fi
      cp "$COMFYUI_OUTPUT_DIR/$FILENAME" "$OUTPUT"
      echo "$OUTPUT"
      exit 0
    fi
  fi

  sleep 5
  ELAPSED=$((ELAPSED + 5))
  echo "Waiting... ${ELAPSED}s" >&2
done

echo "Error: generation timed out after ${TIMEOUT}s" >&2
exit 1
