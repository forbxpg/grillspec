# How the bootstrap works

At the start of every session — and again after `/clear` or a context compaction —
grillspec puts three things into the agent's context:

1. the body of the `using-grillspec` router skill;
2. one status line, for example
   `grillspec: phase=spec change=2026-10-17-login next=write and approve the spec`,
   and the exact command for running the grillspec CLI on this machine;
3. one `WARNING:` line per problem found (an unknown config key, an unreadable state
   file, a missing Python).

## Why a full router

Skills load on demand: an agent sees only each skill's short description and decides
by itself whether to open one. That is cheap, and it fails exactly when it matters —
an agent sure that a change is "obvious" never opens the skill that would have asked
about it. The router closes that gap. It is in context from the first message, and
its one rule is checkable: *if the request involves choosing between options, the
choice belongs to the user*. The table in the router then sizes the response: just do
it, a quick question in chat, or the full pipeline.

The alternative — a ten-line pointer instead of the full router — costs fewer tokens
and triggers less reliably. grillspec chose reliability; the next section is the price.

## What it costs

The router is about 730 words, roughly a thousand tokens, paid once per session and
once per compaction. The status line and warnings add a few dozen. Measured numbers
for whole sessions, with and without grillspec, arrive with the token-economics
benchmark.

## With other workflow plugins

Superpowers and similar plugins inject their own router. Two routers compete for the
same decisions, so grillspec's router tells the agent to ask you to keep only one
enabled, and to follow grillspec for planning until you do.

## The status line

The line comes from `grillspec status`. The phase is derived, never stored: no active
change → `idle`; grill not confirmed → `grill`; spec not approved → `spec`; plan not approved → `plan`; unchecked
plan steps → `execute`; all checked → `done`. Approvals live in
`.grillspec/changes/<id>.toml`; the active change of this working tree lives in
`.grillspec/state.json`, which git ignores, so each worktree has its own.

## Fail-open

A hook that crashes or blocks would take the agent down with it, so the bootstrap never
does either:

- **No Python 3.11+** — the hook runner says so in the context ("gates are OFF") using
  plain shell, and exits successfully.
- **A broken config or state file** — the problem becomes a `WARNING:` line; the router
  still loads.
- **Any other error** — reported as "grillspec bootstrap failed: …"; the session goes on.

## Per harness

| Harness | How the context arrives |
|---|---|
| Claude Code | `SessionStart` hook (`hooks/hooks.json`) |
| Codex | `SessionStart` hook (`hooks/hooks-codex.json`), after you trust it in `/hooks` |
| Cursor | `sessionStart` hook (`hooks/hooks-cursor.json`) |
| Antigravity | `SessionStart` hook (`hooks.json` at the plugin root) |
| GigaCode | an import line in `GIGACODE.md` that loads the router; no status line |
