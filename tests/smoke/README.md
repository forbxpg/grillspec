# Harness smoke tests

`smoke.sh <harness>` starts the harness headless in a throwaway git repository and asks
it to repeat the `grillspec:` status line it received at session start. PASS means the
bootstrap reached the agent in that harness.

- `claude` loads the plugin from this checkout with `--plugin-dir`; nothing is installed.
- `cursor` loads the plugin from this checkout with `--plugin-dir` too.
- `antigravity` copies the skills into the temp project and points workspace hooks
  (`.agents/hooks.json`) at this checkout's runner.
- `codex` needs grillspec installed through its plugin system first (see `docs/en/installation.md`); Codex also needs the hooks trusted.
- `gigacode` is installed into the temp repo by the script itself.

These runs use your own credentials and cost tokens, so they are not part of CI.
Record every run below; unverified harness facts in the umbrella spec are updated from
these results.

## Results

| Date | Harness | Version | Result | Note |
|---|---|---|---|---|
| 2026-10-17 | Claude Code | 2.1.287 (Claude Code) | PASS | |
| 2026-10-17 | Codex | 0.149.1 | not run | CLI present but not authenticated (401) |
| 2026-10-17 | Cursor | — | not run | `cursor-agent` not installed |
| 2026-10-17 | Antigravity | — | not run | `agy` not installed; headless flag `-p` unverified |
| 2026-10-17 | GigaCode | — | not run | `gigacode` not installed; headless flag `-p` unverified |
| 2026-10-18 | Cursor | 2026.10.16-e3cb207 (`cursor-agent`) | PASS | `-p --trust --plugin-dir` |
| 2026-10-18 | Codex | 0.149.1 | not run | not logged in |
| 2026-10-18 | Antigravity | — | not run | `agy` not installed |
| 2026-10-18 | Antigravity | `agy` 1.4.2 | PASS | workspace hooks in the temp project (no `--plugin-dir` in agy) |
| 2026-10-18 | GigaCode | 0.13.1 | not run | not logged in |

## Phase gates

`smoke_gates.sh <harness>` puts a throwaway project's change in the `grill` phase and
asks the agent to write `src/app.py`. PASS means the file was not written and the
agent saw the `grillspec gate:` refusal.

| Date | Harness | Version | Result | Note |
|---|---|---|---|---|
| 2026-10-18 | Claude Code | 2.1.287 (Claude Code) | PASS | `--permission-mode acceptEdits` |
| 2026-10-18 | Codex | 0.149.1 | not run | not logged in; plugin hooks also need `/hooks` approval |
| 2026-10-18 | Cursor | 2026.10.16-e3cb207 (`cursor-agent`) | PASS | `-p --trust --force --plugin-dir` |
| 2026-10-18 | Antigravity | `agy` 1.4.2 | PASS | `--dangerously-skip-permissions` in the temp project, so only the gate can refuse |
