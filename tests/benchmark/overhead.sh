#!/bin/bash
# Measure grillspec's per-session context overhead with the harness's own usage numbers.
# Usage: tests/benchmark/overhead.sh claude
# Runs a trivial prompt in a throwaway git repository without and with grillspec and
# prints input tokens (input + cache creation + cache read) for both. Costs tokens on
# your account; not part of CI. Record results in docs/{en,ru}/tokens.md.
set -euo pipefail
HARNESS="${1:?usage: overhead.sh claude}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
git init -q
PROMPT='Reply with OK only.'

usage() {
  python3 -c '
import json, sys
data = json.load(sys.stdin)
u = data.get("usage", {})
print(sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")))
'
}

case "$HARNESS" in
  claude)
    without="$(claude -p "$PROMPT" --output-format json </dev/null | usage)"
    with="$(claude -p "$PROMPT" --plugin-dir "$REPO" --output-format json </dev/null | usage)"
    version="$(claude --version | head -1)"
    ;;
  *) echo "not wired yet: $HARNESS" >&2; exit 2 ;;
esac

echo "$(date +%F) | $version | without $without | with $with | overhead $((with - without))"
