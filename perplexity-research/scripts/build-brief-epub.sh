#!/usr/bin/env bash
# build-brief-epub.sh - build a research brief markdown file into an .epub.
#
# Usage: build-brief-epub.sh <brief.md> [output.epub]
#
# Reads title, author and date from the markdown's YAML frontmatter when they
# are there, and falls back to the configured author line and today's date.
# Prints the epub path on stdout; everything else goes to stderr, so
# EPUB=$(build-brief-epub.sh brief.md) captures just the path.
#
# Config comes from the plugin's configSchema as env vars, all with defaults:
#   RESEARCH_PANDOC_BIN   pandoc binary            (default: pandoc)
#   RESEARCH_TOC_DEPTH    table-of-contents depth  (default: 2)
#   RESEARCH_AUTHOR_LINE  epub author metadata     (default: empty)
#   RESEARCH_LANGUAGE     BCP 47 language tag      (default: en-US)

set -euo pipefail

SRC="${1:-}"
if [[ -z "$SRC" ]]; then
  echo "Usage: build-brief-epub.sh <brief.md> [output.epub]" >&2
  exit 2
fi

if [[ ! -f "$SRC" ]]; then
  echo "Error: brief markdown not found at $SRC" >&2
  exit 1
fi

PANDOC="${RESEARCH_PANDOC_BIN:-pandoc}"
if ! command -v "$PANDOC" >/dev/null 2>&1; then
  echo "Error: pandoc not found (looked for '$PANDOC')." >&2
  echo "       Install it, or set research pandoc_bin to an absolute path." >&2
  exit 1
fi

OUT="${2:-${SRC%.md}.epub}"
TOC_DEPTH="${RESEARCH_TOC_DEPTH:-2}"
LANGUAGE="${RESEARCH_LANGUAGE:-en-US}"

# Frontmatter wins when present. This is a deliberately small parser: it reads
# the leading YAML block only, and only the three keys pandoc needs. Anything
# more and it would be reimplementing a YAML parser in sed.
frontmatter_value() {
  awk -v key="$1" '
    NR == 1 && $0 != "---" { exit }
    NR == 1 { infm = 1; next }
    infm && $0 == "---" { exit }
    infm {
      idx = index($0, ":")
      if (idx == 0) next
      k = substr($0, 1, idx - 1)
      if (k != key) next
      v = substr($0, idx + 1)
      gsub(/^[ \t]+|[ \t]+$/, "", v)
      gsub(/^"|"$/, "", v)
      print v
      exit
    }
  ' "$SRC"
}

TITLE="$(frontmatter_value title)"
AUTHOR="$(frontmatter_value author)"
DATE="$(frontmatter_value date)"

[[ -n "$TITLE" ]]  || TITLE="$(basename "${SRC%.md}")"
[[ -n "$AUTHOR" ]] || AUTHOR="${RESEARCH_AUTHOR_LINE:-}"
[[ -n "$DATE" ]]   || DATE="$(date +%Y-%m-%d)"

# An em dash inside a brief is a house-style failure, not a build failure, so
# this warns rather than exits. Silent would be worse - the whole point of
# catching it here is that nobody proofreads an epub on an e-reader.
#
# The pattern is the UTF-8 byte sequence for U+2014 rather than the literal
# character, so this file stays greppable-clean for the same character it is
# looking for. $'...' hex escapes work back to bash 3.2.
EM_DASH=$'\xe2\x80\x94'
if grep -q "$EM_DASH" "$SRC"; then
  echo "WARN: $SRC contains em dashes. House style is ' - ' (space-dash-space)." >&2
fi

mkdir -p "$(dirname "$OUT")"

PANDOC_ARGS=(
  "$SRC"
  -o "$OUT"
  --metadata "title=$TITLE"
  --metadata "date=$DATE"
  --metadata "lang=$LANGUAGE"
  --toc
  --toc-depth="$TOC_DEPTH"
)
[[ -n "$AUTHOR" ]] && PANDOC_ARGS+=(--metadata "author=$AUTHOR")

echo "Building $OUT ..." >&2
"$PANDOC" "${PANDOC_ARGS[@]}"

if [[ ! -s "$OUT" ]]; then
  echo "Error: pandoc produced an empty file at $OUT" >&2
  exit 1
fi

SIZE_KB=$(( $(wc -c < "$OUT") / 1024 ))
echo "Built ${SIZE_KB}KB epub" >&2

# A fast-path brief lands around 10-50KB. Very small usually means the source
# was mostly frontmatter, which is a real failure wearing a success exit code.
if [[ "$SIZE_KB" -lt 5 ]]; then
  echo "WARN: ${SIZE_KB}KB is smaller than a real brief. Check the source markdown" >&2
  echo "      actually has body content and not just frontmatter." >&2
fi

echo "$OUT"
