#!/usr/bin/env bash
# run-plugin-tests.sh - discover and run every plugin's own test suite.
#
# Why this exists: the plugin test suites in this repo were never run here.
# `behalfbot`'s shell-tests.yml runs plugins/dating/tests/test-emulator-state.sh
# against its VENDORED copy, so the downstream consumer was testing the code
# and the source of truth was not. A contributor changing emulator-state.sh in
# this repo got no signal at all.
#
# Discovery rather than an enumerated list. behalfbot's shell-tests.yml carries
# a 16-entry `paths:` list duplicated across two triggers, and every new test
# is a silent no-op until someone remembers to add it there. Here a suite is
# picked up by existing at <plugin>/tests/test-*.sh or <plugin>/tests/test_*.py.
#
# The anti-silent-pass guard: a discovery runner that finds nothing exits 0 and
# reports success, which is the "check that cannot fail" failure mode this repo
# already guards against with scanner-self-test and dco-self-test. So this
# script REFUSES when it discovers zero suites. If a legitimate change removes
# the last test suite, lower MIN_SUITES deliberately in the same commit.
#
# Suites must be self-contained: no network, no emulator, no docker, stdlib
# only. Both current suites already meet that bar (the python one mocks the
# Haiku API, the shell one stubs adb on PATH).
#
# Usage:
#   bash .github/scripts/run-plugin-tests.sh          # run everything
#   MIN_SUITES=0 bash .github/scripts/run-plugin-tests.sh   # allow zero

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

MIN_SUITES="${MIN_SUITES:-1}"

# Sorted so the run order is deterministic and the log is diffable between runs.
#
# `while read` rather than mapfile/readarray: macOS ships bash 3.2, where
# mapfile does not exist. CI runs bash 5 and would not have caught it, but a
# contributor running this locally on a Mac would hit "mapfile: command not
# found" and reasonably conclude the runner is broken. Same reason the arrays
# below are seeded as empty strings rather than `()` - `set -u` plus an empty
# array is an unbound-variable error on 3.2.
SHELL_SUITES=""
PY_SUITES=""
while IFS= read -r f; do
    [ -n "$f" ] && SHELL_SUITES="${SHELL_SUITES}${f}"$'\n'
done < <(find . -path ./.git -prune -o -path './*/tests/test-*.sh' -print 2>/dev/null | sort)
while IFS= read -r f; do
    [ -n "$f" ] && PY_SUITES="${PY_SUITES}${f}"$'\n'
done < <(find . -path ./.git -prune -o -path './*/tests/test_*.py' -print 2>/dev/null | sort)

count_lines() {
    # $1 newline-delimited list, possibly empty. Echoes the entry count.
    [ -z "$1" ] && { echo 0; return; }
    printf '%s' "$1" | grep -c ''
}

# .github/scripts/test-check-dco.sh and scripts/test-scan-added-lines.sh are
# NOT matched: they live outside <plugin>/tests/ and already run as the
# dco-self-test and scanner-self-test jobs. Running them twice would just make
# a failure report in two places.

N_SHELL=$(count_lines "$SHELL_SUITES")
N_PY=$(count_lines "$PY_SUITES")
TOTAL=$(( N_SHELL + N_PY ))

printf 'Discovered %d test suite(s): %d shell, %d python\n\n' \
    "$TOTAL" "$N_SHELL" "$N_PY"

if (( TOTAL < MIN_SUITES )); then
    printf 'FAIL: discovered %d suite(s), expected at least %d.\n' "$TOTAL" "$MIN_SUITES" >&2
    printf '\n' >&2
    printf 'A test runner that finds nothing and exits 0 manufactures confidence.\n' >&2
    printf 'Either a suite moved out of <plugin>/tests/, or the discovery globs\n' >&2
    printf 'need updating. If removing the last suite is intentional, lower\n' >&2
    printf 'MIN_SUITES in the workflow in the same commit.\n' >&2
    exit 1
fi

FAILED=""
N_PASSED=0
N_FAILED=0

run_suite() {
    # $1 label, $2... command
    label="$1"; shift
    printf '=== %s\n' "$label"
    if "$@"; then
        printf -- '--- PASS: %s\n\n' "$label"
        N_PASSED=$(( N_PASSED + 1 ))
    else
        rc=$?
        printf -- '--- FAIL: %s (exit %d)\n\n' "$label" "$rc"
        N_FAILED=$(( N_FAILED + 1 ))
        FAILED="${FAILED}  ${label}"$'\n'
    fi
}

while IFS= read -r suite; do
    [ -n "$suite" ] && run_suite "$suite" bash "$suite"
done <<< "$SHELL_SUITES"

# Both current suites resolve their imports relative to __file__, so no
# PYTHONPATH juggling is needed.
while IFS= read -r suite; do
    [ -n "$suite" ] && run_suite "$suite" python3 "$suite"
done <<< "$PY_SUITES"

printf '===========================================\n'
printf 'passed: %d   failed: %d   total: %d\n' "$N_PASSED" "$N_FAILED" "$TOTAL"

if [ "$N_FAILED" -gt 0 ]; then
    printf '\nFailed suites:\n%s' "$FAILED"
    exit 1
fi

printf 'All plugin test suites passed.\n'
