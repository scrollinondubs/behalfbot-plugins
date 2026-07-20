#!/usr/bin/env bash
# setup.sh - loom-vision dependency setup.
#
# Idempotent: re-running is a no-op when deps are already present.
# Invoked by the chassis activate-plugins.sh on every bootstrap when
# modules.loom-vision.enabled == true.
#
# Linux-first (the chassis container is Debian slim). No brew fallback -
# on hosts without a supported package path, missing deps produce a clear
# ERROR with manual instructions instead of a platform-specific install
# attempt (behalfbot#53 / new-jaxity#303 review finding).
#
# Version pinning: loom-dl is pinned. The plugins repo pin covers plugin
# SOURCE; pinning setup deps keeps the dependency layer from drifting
# underneath it (two installs fetching the same tag must run the same
# loom-dl).

set -euo pipefail

LOOM_DL_VERSION="1.1.1"

echo "[loom-vision] checking deps..."

fail=0

# node - runs the transcript JSON -> VTT conversion, and npm ships with it.
if command -v node >/dev/null 2>&1; then
  echo "[loom-vision] node present ($(node --version 2>/dev/null || echo 'unknown version'))"
else
  echo "[loom-vision] ERROR: node not found. Install Node.js via your platform's" >&2
  echo "[loom-vision]        package manager (Debian: apt-get install nodejs npm)." >&2
  fail=1
fi

# ffmpeg - frame sampling + ffprobe. Baked into the chassis image; on other
# hosts install manually.
if command -v ffmpeg >/dev/null 2>&1; then
  echo "[loom-vision] ffmpeg present ($(ffmpeg -version 2>/dev/null | head -1))"
else
  echo "[loom-vision] ERROR: ffmpeg not found. Install it via your platform's" >&2
  echo "[loom-vision]        package manager (Debian: apt-get install ffmpeg)." >&2
  fail=1
fi

# loom-dl - Node CLI, installed via npm at a PINNED version.
if command -v loom-dl >/dev/null 2>&1; then
  echo "[loom-vision] loom-dl present ($(loom-dl --version 2>/dev/null || echo 'unknown version'))"
elif command -v npm >/dev/null 2>&1; then
  echo "[loom-vision] installing loom-dl@${LOOM_DL_VERSION} via npm..."
  npm install -g "loom-dl@${LOOM_DL_VERSION}"
else
  echo "[loom-vision] ERROR: loom-dl not found and npm unavailable to install it." >&2
  echo "[loom-vision]        Install Node.js first, then: npm install -g loom-dl@${LOOM_DL_VERSION}" >&2
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  echo "[loom-vision] setup incomplete - see errors above." >&2
  exit 1
fi

echo "[loom-vision] setup complete."
