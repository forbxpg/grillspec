#!/bin/sh
# Smoke test: does a harness receive grillspec's session-start status line?
# Usage: tests/smoke/smoke.sh <claude|codex|cursor|antigravity|gigacode>
# Runs the harness headless in a throwaway project and prints PASS or FAIL.
# claude loads the plugin with --plugin-dir and changes nothing outside the temp dir;
# the other harnesses need grillspec installed first (see docs/en/installation.md).
set -eu
HARNESS="${1:?usage: smoke.sh <harness>}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
git init -q
PROMPT='Reply with the first line starting with "grillspec:" that you were given at session start, or NONE.'
EXPECT='grillspec: phase='
if [ "$HARNESS" = gigacode ]; then
  # GigaCode loads the router through GIGACODE.md and gets no status line.
  PROMPT='Reply with the first "#" heading of the grillspec router skill you were given, or NONE.'
  EXPECT='Using grillspec'
fi

case "$HARNESS" in
  claude) REPLY="$(claude -p --plugin-dir "$REPO" "$PROMPT" 2>&1 || true)" ;;
  codex) REPLY="$(codex exec --skip-git-repo-check "$PROMPT" </dev/null 2>&1 || true)" ;;
  cursor) REPLY="$(cursor-agent -p --trust --plugin-dir "$REPO" "$PROMPT" </dev/null 2>&1 || true)" ;;
  antigravity) REPLY="$(agy -p "$PROMPT" 2>&1 || true)" ;;
  gigacode)
    sh "$REPO/scripts/grillspec" install --harness gigacode >/dev/null
    REPLY="$(gigacode -p "$PROMPT" 2>&1 || true)"
    ;;
  *) echo "unknown harness: $HARNESS" >&2; exit 2 ;;
esac

if printf '%s' "$REPLY" | grep -q "$EXPECT"; then
  echo "PASS $HARNESS"
else
  echo "FAIL $HARNESS"
  printf '%s\n' "$REPLY" | tail -5
  exit 1
fi
