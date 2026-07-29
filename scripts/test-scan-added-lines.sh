#!/usr/bin/env bash
# test-scan-added-lines.sh - prove the credential scanner fires AND stays quiet.
#
# A scanner is only worth having if you have watched it fail. Both directions
# are tested here because both have already been wrong once: the ALLOW pattern
# originally used \b anchors around `${VAR}` and `<token>`, which cannot match -
# \b needs a word character on one side and those start with a symbol - so every
# `password = "${VAULT_PASSWORD}"` was a false positive until the positive
# control caught it.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCANNER="$HERE/scan-added-lines.py"
pass=0
fail=0

expect_exit() {
    local want="$1" name="$2" input="$3"
    local got
    printf '%s\n' "$input" | python3 "$SCANNER" >/dev/null 2>&1
    got=$?
    if [[ "$got" == "$want" ]]; then
        echo "  ok    $name"
        pass=$((pass + 1))
    else
        echo "  FAIL  $name (wanted exit $want, got $got)"
        fail=$((fail + 1))
    fi
}

echo "Negative controls - these MUST be caught (exit 1):"
expect_exit 1 "anthropic key"       '+++ b/a.sh
+API_KEY="sk-ant-api03-QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ"'
expect_exit 1 "aws access key id"   '+++ b/a.sh
+aws_key = "AKIAIOSFODNN7EXAMPLE"'
expect_exit 1 "private key block"   '+++ b/a.pem
+-----BEGIN RSA PRIVATE KEY-----'
expect_exit 1 "github token"        '+++ b/a.sh
+GH=ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
# Exactly 35 chars after the AIza prefix. The first draft of this fixture had
# 34 and silently passed the scanner, which the test then reported as a scanner
# bug. It was a fixture bug - worth the comment, because the next person to
# shorten this string will reintroduce it.
expect_exit 1 "google api key"      '+++ b/a.js
+const k = "AIzaSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS"'
expect_exit 1 "generic assignment"  '+++ b/a.yml
+password: "hunter2istooshortbutthisoneislongenough"'

echo
echo "Positive controls - these MUST NOT be caught (exit 0):"
expect_exit 0 "YOUR_API_KEY"        '+++ b/README.md
+export API_KEY="YOUR_API_KEY"'
expect_exit 0 "angle placeholder"   '+++ b/README.md
+token: <your-token-here>'
expect_exit 0 "shell var expansion" '+++ b/a.sh
+password = "${VAULT_PASSWORD}"'
expect_exit 0 "bare env var"        '+++ b/a.sh
+secret = "$GITHUB_TOKEN"'
expect_exit 0 "example literal"     '+++ b/a.yml
+api_key: "example-value-goes-right-here"'
expect_exit 0 "removed line only"   '+++ b/a.sh
-API_KEY="sk-ant-api03-QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ"'

echo
if [[ "$fail" -gt 0 ]]; then
    echo "FAIL: $fail of $((pass + fail)) checks failed"
    exit 1
fi
echo "OK: $pass/$pass checks passed"
