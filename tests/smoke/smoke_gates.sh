#!/bin/sh
# Smoke test: does the phase gate stop a code edit while a change is being grilled?
# Usage: tests/smoke/smoke_gates.sh claude
# Runs the harness headless in a throwaway project whose change is in the grill phase,
# asks it to write src/app.py, and prints PASS when the file was not written.
set -eu
HARNESS="${1:?usage: smoke_gates.sh <harness>}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
git init -q
sh "$REPO/scripts/grillspec" init --backend openspec >/dev/null
sh "$REPO/scripts/grillspec" new add-greeting >/dev/null
PROMPT='Create the file src/app.py containing print("hi"). Do it now without asking questions; if a tool call is refused, quote the refusal.'

case "$HARNESS" in
  claude)
    REPLY="$(claude -p "$PROMPT" --plugin-dir "$REPO" --permission-mode acceptEdits \
      --allowedTools Write Edit Bash 2>&1 </dev/null || true)" ;;
  *) echo "not wired yet: $HARNESS" >&2; exit 2 ;;
esac

if [ ! -e src/app.py ] && printf '%s' "$REPLY" | grep -q "grillspec gate"; then
  echo "PASS $HARNESS"
else
  echo "FAIL $HARNESS"
  [ -e src/app.py ] && echo "src/app.py was written"
  printf '%s\n' "$REPLY" | tail -8
  exit 1
fi
