#!/usr/bin/env bash
# setup.sh - perplexity-research dependency setup.
#
# Idempotent: re-running is a no-op. Invoked by the chassis activate-plugins.sh
# on every bootstrap when modules.perplexity-research.enabled == true.
#
# Linux-first, no brew fallback. pandoc is a hard dependency because the epub is
# the deliverable. pdftotext is soft - without it the deep path loses one rung of
# its fallback chain and nothing else.

set -euo pipefail

echo "[perplexity-research] checking deps..."

fail=0

if command -v "${RESEARCH_PANDOC_BIN:-pandoc}" >/dev/null 2>&1; then
  echo "[perplexity-research] pandoc present ($("${RESEARCH_PANDOC_BIN:-pandoc}" --version 2>/dev/null | head -1))"
else
  echo "[perplexity-research] ERROR: pandoc not found. Install it via your platform's" >&2
  echo "[perplexity-research]        package manager (Debian: apt-get install pandoc)," >&2
  echo "[perplexity-research]        or set pandoc_bin to an absolute path." >&2
  fail=1
fi

if command -v pdftotext >/dev/null 2>&1; then
  echo "[perplexity-research] pdftotext present"
else
  echo "[perplexity-research] WARN: pdftotext not found (Debian: apt-get install" >&2
  echo "[perplexity-research]       poppler-utils). The deep path loses its PDF-rescue" >&2
  echo "[perplexity-research]       fallback; everything else still works." >&2
fi

# Directories the pipeline writes into. Creating them at setup means a run fails
# on something interesting rather than on mkdir.
for dir_var in RESEARCH_OUTPUT_DIR RESEARCH_SCRATCH_DIR; do
  dir="${!dir_var:-}"
  if [[ -n "$dir" ]]; then
    if mkdir -p "$dir" 2>/dev/null; then
      echo "[perplexity-research] $dir_var ready: $dir"
    else
      echo "[perplexity-research] ERROR: cannot create $dir_var at '$dir'." >&2
      fail=1
    fi
  fi
done

# Delivery sanity. Configuring a target the install cannot reach is a silent
# failure at 2am otherwise.
case "${RESEARCH_DELIVERY_TARGETS:-file}" in
  *chat*)
    if [[ -z "${RESEARCH_DELIVERY_CHANNEL_ID:-${DISCORD_PRIMARY_CHANNEL_ID:-}}" ]]; then
      echo "[perplexity-research] WARN: 'chat' is a delivery target but no channel id is" >&2
      echo "[perplexity-research]       configured. Briefs will refuse to post rather than" >&2
      echo "[perplexity-research]       guess a channel. Set delivery_channel_id." >&2
    fi
    ;;
esac

case "${RESEARCH_DELIVERY_TARGETS:-file}" in
  *ereader*)
    cmd="${RESEARCH_EREADER_SEND_COMMAND:-}"
    if [[ -z "$cmd" ]]; then
      echo "[perplexity-research] WARN: 'ereader' is a delivery target but" >&2
      echo "[perplexity-research]       ereader_send_command is unset." >&2
    elif ! command -v "${cmd%% *}" >/dev/null 2>&1 && [[ ! -x "${cmd%% *}" ]]; then
      echo "[perplexity-research] WARN: ereader_send_command '${cmd%% *}' is not executable." >&2
    fi
    ;;
esac

if [[ "$fail" -ne 0 ]]; then
  echo "[perplexity-research] setup incomplete - see errors above." >&2
  exit 1
fi

echo "[perplexity-research] setup complete."
