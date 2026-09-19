#!/usr/bin/env bash
# setup.sh - video-explainer dependency setup. Idempotent: a second run is a no-op.
#
#   ./setup.sh              set up the slide path (the default, no licensed deps)
#   ./setup.sh --remotion   additionally set up the animated path (license gate)
#
# Nothing third party is vendored into this repo. ffmpeg comes from the system
# package manager and Remotion comes from npm, so every install acquires them
# under its own licence rather than receiving a copy from here. See LICENSING.md.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PILLOW_VERSION="11.3.0"
WANT_REMOTION=0
FAIL=0

for arg in "$@"; do
  case "$arg" in
    --remotion) WANT_REMOTION=1 ;;
    *) echo "[video-explainer] ERROR: unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log()  { echo "[video-explainer] $1"; }
warn() { echo "[video-explainer] WARN: $1" >&2; }
err()  { echo "[video-explainer] ERROR: $1" >&2; FAIL=1; }

apt_install() {
  if ! command -v apt-get >/dev/null 2>&1; then
    return 1
  fi
  if [[ "$(id -u)" -eq 0 ]]; then
    apt-get install -y "$@" >/dev/null 2>&1
  elif command -v sudo >/dev/null 2>&1; then
    sudo apt-get install -y "$@" >/dev/null 2>&1
  else
    return 1
  fi
}

pip_install() {
  # PEP 668 marks distro and Homebrew Pythons externally managed, so a bare
  # install fails there. Same escape hatch flight-search uses.
  if pip3 install "$@" >/dev/null 2>&1; then return 0; fi
  pip3 install --break-system-packages "$@" >/dev/null 2>&1
}

# ---------------------------------------------------------------- slide path

if command -v python3 >/dev/null 2>&1; then
  log "python3 present ($(python3 --version 2>&1))"
else
  err "python3 not found. Install it with your platform's package manager."
fi

if python3 -c "import PIL" >/dev/null 2>&1; then
  log "Pillow present ($(python3 -c 'import PIL; print(PIL.__version__)' 2>/dev/null))"
elif command -v pip3 >/dev/null 2>&1; then
  log "installing Pillow==${PILLOW_VERSION}..."
  if pip_install "Pillow==${PILLOW_VERSION}"; then
    log "Pillow installed"
  else
    err "Pillow install failed. Try: apt-get install -y python3-pil, or a virtualenv."
  fi
else
  err "Pillow not found and pip3 unavailable to install it."
fi

for bin in ffmpeg ffprobe; do
  if command -v "$bin" >/dev/null 2>&1; then
    log "$bin present"
  else
    log "$bin not found, attempting install via apt-get..."
    apt_install ffmpeg
    if command -v "$bin" >/dev/null 2>&1; then
      log "$bin installed"
    else
      err "$bin not found. Install ffmpeg with your platform's package manager."
    fi
  fi
done

# Narration engine. Soft: warn rather than fail, because which engine is right
# depends on the install and one of them needs no setup at all.
if [[ -n "${VIDEO_EXPLAINER_TTS_BIN:-}" && -x "${VIDEO_EXPLAINER_TTS_BIN}" ]]; then
  log "narration: host script at \$VIDEO_EXPLAINER_TTS_BIN"
elif [[ -n "${OPENAI_API_KEY:-}" ]]; then
  log "narration: OpenAI credential present in the environment"
elif command -v say >/dev/null 2>&1; then
  warn "narration: falling back to the macOS 'say' command. Free and offline, but robotic. Set OPENAI_API_KEY for a better voice."
else
  warn "narration: no engine available. Set OPENAI_API_KEY, or point \$VIDEO_EXPLAINER_TTS_BIN at your own script. Rendering will fail until one of those is true."
fi

# ------------------------------------------------------------- animated path

if [[ $WANT_REMOTION -eq 1 ]]; then
  cat <<'GATE'

[video-explainer] ------------------------------------------------------------
[video-explainer] Remotion is source-available software, not open source, and
[video-explainer] it is licensed per organization.
[video-explainer]
[video-explainer] The Free Licence covers individuals (personal or commercial),
[video-explainer] organizations of up to 3 people, non-profits, and anyone still
[video-explainer] evaluating it. Organizations of 4 or more need a paid Company
[video-explainer] Licence from remotion.pro.
[video-explainer]
[video-explainer] Note that `remotion render`, which this skill calls, counts as
[video-explainer] an "automation" under Remotion's terms. For an organization
[video-explainer] that is not Free Licence eligible that is the per-render tier,
[video-explainer] not the per-seat one.
[video-explainer]
[video-explainer] This prompt is disclosure, not enforcement. It is here so that
[video-explainer] nobody installs a licensed dependency without being told it is
[video-explainer] one. Detail in LICENSING.md.
[video-explainer] ------------------------------------------------------------

GATE
  ACK="${VIDEO_EXPLAINER_REMOTION_LICENSE_ACK:-}"
  if [[ -z "$ACK" ]]; then
    if [[ -t 0 ]]; then
      read -r -p "[video-explainer] Are you eligible for the Remotion Free Licence, or do you hold a Company Licence? [y/N] " ACK
    else
      warn "not a terminal and VIDEO_EXPLAINER_REMOTION_LICENSE_ACK is unset, skipping the animated path."
      warn "set VIDEO_EXPLAINER_REMOTION_LICENSE_ACK=yes to install it non-interactively."
      ACK="n"
    fi
  fi

  case "$ACK" in
    y|Y|yes|YES|true|1)
      if ! command -v npm >/dev/null 2>&1; then
        log "npm not found, attempting install via apt-get..."
        apt_install nodejs npm
      fi
      if command -v npm >/dev/null 2>&1; then
        if [[ -d "${SCRIPT_DIR}/remotion-template/node_modules" ]]; then
          log "Remotion already installed in remotion-template/"
        else
          log "installing Remotion from the lockfile (npm ci)..."
          if (cd "${SCRIPT_DIR}/remotion-template" && npm ci --no-audit --no-fund >/dev/null 2>&1); then
            log "Remotion installed"
          else
            err "npm ci failed. If it reports a lockfile mismatch that is the pin doing its job; regenerate the lockfile deliberately rather than running npm install to paper over it."
          fi
        fi
      else
        err "npm not found and could not be installed. The animated path needs Node; the slide path does not."
      fi
      ;;
    *)
      log "animated path skipped. The slide path works without it."
      ;;
  esac
fi

echo
if [[ $FAIL -eq 0 ]]; then
  log "setup complete."
else
  log "setup finished with errors above."
fi
exit $FAIL
