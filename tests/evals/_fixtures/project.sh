#!/bin/bash
# A small project set up for grillspec (superpowers backend). With "active", it also
# has a change in the grill phase with two open questions. "council" is "active" at
# deep depth with a role-only council and external members turned off. "grilled" has
# a confirmed grill ready for the spec; "deferred" is the same with a deferred
# decision that the retry requirement depends on.
set -euo pipefail
git init -q .
git config user.email t@t && git config user.name t
mkdir -p .grillspec src
printf 'version = 1\n[spec]\nbackend = "superpowers"\n' > .grillspec/config.toml
printf '.grillspec/state.json\n' > .gitignore
cat > src/api.py <<'PY'
def fetch_user(user_id: int) -> dict:
    return {"id": user_id}
PY
meta="depth=standard council=no budget=15 asked=1"
if [ "${1:-}" = council ]; then
  meta="depth=deep council=yes budget=none asked=1 council_calls=0"
  cat >> .grillspec/config.toml <<'TOML'
[council]
enabled = "yes"
members = ["role:simplicity", "role:devil", "role:risk"]
external = "never"
TOML
fi
if [ "${1:-}" = active ] || [ "${1:-}" = council ]; then
  mkdir -p docs/grillspec/specs .grillspec/changes
  cat > docs/grillspec/specs/2026-10-17-webhooks.md <<MD
# 2026-10-17-webhooks

## Decision log

<!-- grillspec: $meta -->

### Open
- [ ] Q1 Retry policy for failed webhook deliveries
- [ ] Q2 Log format for delivery attempts

### Settled
- [x] D1 Delivery guarantee — **at-least-once** · user
MD
  printf 'version = 1\n' > .grillspec/changes/2026-10-17-webhooks.toml
  printf '{"version": 1, "active": "2026-10-17-webhooks"}\n' > .grillspec/state.json
fi
if [ "${1:-}" = grilled ] || [ "${1:-}" = deferred ]; then
  mkdir -p docs/grillspec/specs .grillspec/changes
  open=""
  retry="three times with exponential backoff, 1 s then 2 s then 4 s"
  if [ "${1:-}" = deferred ]; then
    open="- [ ] Q3 Maximum retry window · deferred"
    retry="with exponential backoff until the window from Q3 runs out"
  fi
  cat > docs/grillspec/specs/2026-10-17-webhooks.md <<MD
# 2026-10-17-webhooks

## Decision log

<!-- grillspec: depth=standard council=no budget=15 asked=3 -->

### Open
$open

### Settled
- [x] D1 Delivery guarantee — **at-least-once** · user
- [x] D2 Retry policy — **retry failed deliveries $retry** · user
- [x] D3 Attempt log — **one JSON line per attempt with status code and duration** · accepted
MD
  printf 'version = 1\ngrilled = 2026-10-17\n' > .grillspec/changes/2026-10-17-webhooks.toml
  printf '{"version": 1, "active": "2026-10-17-webhooks"}\n' > .grillspec/state.json
fi
git add -A && git commit -qm init
