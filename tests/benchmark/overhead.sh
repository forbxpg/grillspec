#!/bin/bash
# Measure grillspec's per-session context overhead with the harness's own usage numbers.
# Usage: tests/benchmark/overhead.sh claude
# Runs a trivial prompt in a throwaway git repository without and with grillspec and
# prints input tokens (input + cache creation + cache read) for both. Costs tokens on
# your account; not part of CI. Record results in docs/{en,ru}/tokens.md.
set -euo pipefail
HARNESS="${1:?usage: overhead.sh claude}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
command -v python3 >/dev/null || { echo "python3 is needed to read the usage JSON" >&2; exit 2; }
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
git init -q
PROMPT='Reply with OK only.'

# Print "<input tokens> <model>" from a result JSON; fail on an error result.
usage() {
  python3 -c '
import json, sys
data = json.load(sys.stdin)
usage = data.get("usage")
if data.get("is_error") or not usage:
    sys.exit("the run failed: " + str(data.get("result", data))[:200])
total = sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
print(total, ",".join(sorted(data.get("modelUsage", {}))) or "unknown")
'
}

case "$HARNESS" in
  claude)
    enabled="$(claude plugin list --json 2>/dev/null | python3 -c '
import json, sys
print(any(p.get("enabled") and p.get("id", "").startswith("grillspec@") for p in json.load(sys.stdin)))
' || echo False)"
    if [ "$enabled" = True ]; then
      echo "grillspec is enabled as a plugin, so the 'without' run would include it;" >&2
      echo "disable it (claude plugin disable grillspec@grillspec) and run again" >&2
      exit 2
    fi
    read -r without model < <(claude -p "$PROMPT" --strict-mcp-config --output-format json </dev/null | usage)
    read -r with _ < <(claude -p "$PROMPT" --strict-mcp-config --plugin-dir "$REPO" --output-format json </dev/null | usage)
    version="$(claude --version | head -1)"
    ;;
  *) echo "not wired yet: $HARNESS" >&2; exit 2 ;;
esac

echo "$(date +%F) | $version | $model | without $without | with $with | overhead $((with - without))"
