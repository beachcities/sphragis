#!/usr/bin/env bash
# Smoke test for the *installed* sphragis CLI.
#
# Run after `pip install <wheel>` in a clean environment, from the repo root
# (the bundled examples/ directory is used as input). Verifies:
#   - `sphragis inspect` works
#   - `sphragis evaluate` produces allow / allow_with_obligations / deny
#     with the documented exit codes (0 / 0 / 1)
#   - an invalid root and an unsupported spec version produce a JSON error
#     on stderr with exit code 2, and never a traceback
set -u

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

command -v sphragis >/dev/null || fail "sphragis CLI not on PATH"

# --- inspect -----------------------------------------------------------------
out=$(sphragis inspect examples/restricted_case.dclg) || fail "inspect exited non-zero"
echo "$out" | grep -q '"pii_status"' || fail "inspect output missing pii_status"
echo "$out" | grep -q '"spec_version": "0.7"' || fail "inspect output missing spec_version"

# --- evaluate: allow ---------------------------------------------------------
out=$(sphragis evaluate examples/open_minimal.dclg --op rag_index)
[ $? -eq 0 ] || fail "rag_index on open_minimal should exit 0"
echo "$out" | grep -q '"verdict": "allow"' || fail "expected verdict allow"

# --- evaluate: allow_with_obligations ---------------------------------------
out=$(sphragis evaluate examples/open_minimal.dclg --op train)
[ $? -eq 0 ] || fail "train on open_minimal should exit 0"
echo "$out" | grep -q '"verdict": "allow_with_obligations"' \
  || fail "expected verdict allow_with_obligations"
echo "$out" | grep -q 'training_provenance_required' \
  || fail "expected training_provenance_required obligation"

# --- evaluate: deny ----------------------------------------------------------
out=$(sphragis evaluate examples/restricted_case.dclg --op extract --involves-pii)
[ $? -eq 1 ] || fail "PII extract on restricted_case should exit 1"
echo "$out" | grep -q '"verdict": "deny"' || fail "expected verdict deny"

# --- error handling: invalid root -------------------------------------------
tmp=$(mktemp --suffix=.dclg)
printf '<not_doclang><head/></not_doclang>' > "$tmp"
err=$(sphragis evaluate "$tmp" --op rag_index 2>&1 >/dev/null)
code=$?
rm -f "$tmp"
[ $code -eq 2 ] || fail "invalid root should exit 2 (got $code)"
echo "$err" | grep -q '"error"' || fail "invalid root should emit JSON error on stderr"
echo "$err" | grep -q 'Traceback' && fail "invalid root must not print a traceback"

# --- error handling: unsupported spec version --------------------------------
tmp=$(mktemp --suffix=.dclg)
printf '<doclang version="9.9"><head/></doclang>' > "$tmp"
err=$(sphragis inspect "$tmp" 2>&1 >/dev/null)
code=$?
rm -f "$tmp"
[ $code -eq 2 ] || fail "unsupported version should exit 2 (got $code)"
echo "$err" | grep -q '"error"' || fail "unsupported version should emit JSON error on stderr"
echo "$err" | grep -q 'Traceback' && fail "unsupported version must not print a traceback"

echo "SMOKE OK: inspect, allow, allow_with_obligations, deny, and both JSON error paths verified"
