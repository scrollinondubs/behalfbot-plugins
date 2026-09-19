#!/usr/bin/env bash
# The animated path must never install Remotion without an explicit licence
# acknowledgement. This is the one behaviour in setup.sh with a legal
# consequence attached, so it gets a test.
#
# Self-contained: no network, no package manager, no node. Every external
# command setup.sh reaches for is stubbed on PATH, and the npm stub records
# its arguments so the test can prove `npm ci` was never called.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(dirname "$HERE")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

STUBS="$WORK/bin"
RECORD="$WORK/npm-calls"
mkdir -p "$STUBS"
: > "$RECORD"

cat > "$STUBS/npm" <<STUB
#!/usr/bin/env bash
echo "\$@" >> "$RECORD"
exit 0
STUB

for stub in ffmpeg ffprobe pip3; do
  printf '#!/usr/bin/env bash\nexit 0\n' > "$STUBS/$stub"
done

# Stubbed so the Pillow check always passes and never reaches pip.
cat > "$STUBS/python3" <<'STUB'
#!/usr/bin/env bash
case "${1:-}" in
  --version) echo "Python 3.12.0" ;;
  *) : ;;
esac
exit 0
STUB

chmod +x "$STUBS"/*

fails=0
check() {
  if [[ "$2" == "$3" ]]; then
    echo "ok   - $1"
  else
    echo "FAIL - $1 (expected '$3', got '$2')"
    fails=$((fails + 1))
  fi
}

# 1. No acknowledgement, no terminal: must skip, must not call npm.
env -i PATH="$STUBS:/usr/bin:/bin" HOME="$WORK" \
  bash "$PLUGIN_DIR/setup.sh" --remotion < /dev/null > "$WORK/out1" 2>&1
check "unacknowledged run does not install" "$(wc -l < "$RECORD" | tr -d ' ')" "0"
grep -q "skipping the animated path" "$WORK/out1"
check "unacknowledged run says it skipped" "$?" "0"

# 2. Explicitly declined: must also skip.
: > "$RECORD"
env -i PATH="$STUBS:/usr/bin:/bin" HOME="$WORK" \
  VIDEO_EXPLAINER_REMOTION_LICENSE_ACK=no \
  bash "$PLUGIN_DIR/setup.sh" --remotion < /dev/null > "$WORK/out2" 2>&1
check "declined run does not install" "$(wc -l < "$RECORD" | tr -d ' ')" "0"

# 3. The disclosure text must be printed before any decision is taken, on both
#    paths. A silent gate is not a gate.
grep -q "not open source" "$WORK/out1"
check "licence disclosure shown when unacknowledged" "$?" "0"
grep -q "not open source" "$WORK/out2"
check "licence disclosure shown when declined" "$?" "0"

# 4. The slide path must not be gated behind the licence at all.
: > "$RECORD"
env -i PATH="$STUBS:/usr/bin:/bin" HOME="$WORK" \
  bash "$PLUGIN_DIR/setup.sh" < /dev/null > "$WORK/out3" 2>&1
check "slide path setup succeeds with no licence prompt" "$?" "0"
grep -q "not open source" "$WORK/out3"
check "slide path shows no licence prompt" "$?" "1"

if [[ $fails -gt 0 ]]; then
  echo "$fails check(s) failed"
  exit 1
fi
echo "all checks passed"
