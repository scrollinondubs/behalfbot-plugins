#!/usr/bin/env bash
# setup.sh - parse-youtube dependency setup.
#
# Idempotent: re-running is a no-op when deps are already present.
# Invoked by the chassis activate-plugins.sh on every bootstrap when
# modules.parse-youtube.enabled == true.
#
# Linux-first (the chassis container is Debian slim). No brew fallback - on a
# host without a supported package path, a missing dep is a clear ERROR with
# manual instructions rather than a platform-specific install attempt.
#
# Pinning: youtube-transcript-api is pinned exactly, because its 0.x and 1.x
# APIs differ in shape and the script targets 1.x. yt-dlp gets a floor rather
# than an exact pin - YouTube changes its player often enough that an exact pin
# is a scheduled breakage, and yt-dlp is a soft dependency whose failure only
# costs metadata.

set -euo pipefail

YTA_VERSION="1.2.4"
YTDLP_MIN_VERSION="2026.3.17"

echo "[parse-youtube] checking deps..."

fail=0

if command -v python3 >/dev/null 2>&1; then
  echo "[parse-youtube] python3 present ($(python3 --version 2>&1))"
else
  echo "[parse-youtube] ERROR: python3 not found. Install it via your platform's" >&2
  echo "[parse-youtube]        package manager (Debian: apt-get install python3 python3-pip)." >&2
  fail=1
fi

pip_install() {
  # pip on Debian-based images is increasingly PEP 668 managed, which rejects a
  # plain install into the system environment. --break-system-packages is the
  # documented escape hatch and is correct inside a single-purpose container;
  # the fallback keeps the script working on hosts where the flag is unknown.
  if pip3 install "$1" >/dev/null 2>&1; then
    return 0
  fi
  pip3 install --break-system-packages "$1" >/dev/null 2>&1
}

if [[ "$fail" -eq 0 ]]; then
  if python3 -c 'import youtube_transcript_api' >/dev/null 2>&1; then
    echo "[parse-youtube] youtube-transcript-api present"
  elif command -v pip3 >/dev/null 2>&1; then
    echo "[parse-youtube] installing youtube-transcript-api==${YTA_VERSION}..."
    if pip_install "youtube-transcript-api==${YTA_VERSION}"; then
      echo "[parse-youtube] youtube-transcript-api installed"
    else
      echo "[parse-youtube] ERROR: pip install youtube-transcript-api==${YTA_VERSION} failed." >&2
      fail=1
    fi
  else
    echo "[parse-youtube] ERROR: youtube-transcript-api missing and pip3 unavailable." >&2
    echo "[parse-youtube]        Install pip, then: pip3 install youtube-transcript-api==${YTA_VERSION}" >&2
    fail=1
  fi
fi

# yt-dlp is soft: metadata only. A missing one WARNs and the plugin still works.
if command -v yt-dlp >/dev/null 2>&1; then
  echo "[parse-youtube] yt-dlp present ($(yt-dlp --version 2>/dev/null || echo 'unknown version'))"
elif command -v pip3 >/dev/null 2>&1; then
  echo "[parse-youtube] installing yt-dlp>=${YTDLP_MIN_VERSION}..."
  if pip_install "yt-dlp>=${YTDLP_MIN_VERSION}"; then
    echo "[parse-youtube] yt-dlp installed"
  else
    echo "[parse-youtube] WARN: yt-dlp install failed. Transcripts still work;" >&2
    echo "[parse-youtube]       title, channel, duration and chapters will be null." >&2
  fi
else
  echo "[parse-youtube] WARN: yt-dlp not found and pip3 unavailable. Transcripts still" >&2
  echo "[parse-youtube]       work; metadata fields will be null." >&2
fi

if [[ "$fail" -ne 0 ]]; then
  echo "[parse-youtube] setup incomplete - see errors above." >&2
  exit 1
fi

echo "[parse-youtube] setup complete."
