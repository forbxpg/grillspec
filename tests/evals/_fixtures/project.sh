#!/bin/bash
# A small project set up for grillspec (superpowers backend). With "active", it also
# has a change in the grill phase with two open questions.
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
if [ "${1:-}" = active ]; then
  mkdir -p docs/grillspec/specs .grillspec/changes
  cat > docs/grillspec/specs/2026-10-17-webhooks.md <<'MD'
# 2026-10-17-webhooks

## Decision log

<!-- grillspec: depth=standard council=no budget=15 asked=1 -->

### Open
- [ ] Q1 Retry policy for failed webhook deliveries
- [ ] Q2 Log format for delivery attempts

### Settled
- [x] D1 Delivery guarantee — **at-least-once** · user
MD
  printf 'version = 1\n' > .grillspec/changes/2026-10-17-webhooks.toml
  printf '{"version": 1, "active": "2026-10-17-webhooks"}\n' > .grillspec/state.json
fi
git add -A && git commit -qm init
