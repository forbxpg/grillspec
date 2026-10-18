# How phase gates work

While a change is grilled, specced or planned, the agent should be asking and writing
the spec, not coding. The skills say so, and a pre-tool hook backs them up: in those
three phases it blocks edits outside the change's own artifacts and obvious shell
writes, and tells the agent what to finish first.

## When the gate acts

Only when all of these hold:

- `gates.enabled` is `true` (the default; see [Configuration](../configuration.md));
- a change is active and its phase is `grill`, `spec` or `plan`;
- the user has not paused the gate for that change and phase.

In `execute` and `done`, and with no active change, the hook says nothing.

## What may change

| Allowed | Why |
|---|---|
| `.grillspec/`, except `state.json`, `config.toml` and `changes/` | council payloads and other scratch files; only the CLI writes approvals, config and state |
| OpenSpec: `openspec/changes/<id>/**` | the change's proposal, design, deltas and tasks |
| superpowers: `docs/grillspec/specs/<id>.md` and `docs/grillspec/plans/<id>.md` | the change's spec (with its decision log) and plan |
| `docs/grillspec/memory/` | long-form memory written after spec approval |
| paths matching a `gates.allow` glob | your own exceptions, e.g. `["notes/*"]` |
| anything outside the project | not project code |

Approved artifacts stay editable: their approval hashes already catch a change after
approval.

A blocked call gets one line back, for example:

```text
grillspec gate: add-limits is in the spec phase, so only its spec artifacts may change; src/app.py is outside them. Next: write the spec, grillspec validate, then approve. To bypass, the user runs grillspec gate pause in their own terminal.
```

## Shell commands

The hook also reads shell commands and blocks the obvious writers whose target is not
allowed: output redirection (`>`, `>>`, `&>`; `/dev/null` is fine), `tee`, `sed -i`,
`perl -i`, `cp`, `mv`, `rm`, `touch`, `mkdir`, `ln`, `chmod`, the git commands that
change working-tree files (`restore`, `apply`, `clean`, `checkout --`, `reset --hard`,
`stash` other than `list`/`show`, …), Codex `apply_patch`, and PowerShell's file cmdlets
and their aliases. It follows a leading `cd dir &&`, looks inside `bash -c "…"`, and
expands `~` and environment variables. Everything else — `ls`, `git status`,
`git commit`, `git worktree add`, test runs, `grillspec` itself — runs.

**The gate is a guardrail, not a sandbox.** It cannot see a write hidden inside
`python -c` or a script, and it does not try to. Its job is to stop drift, and the
router tells the agent never to work around it.

## Pausing the gate

Only the user can pause it, from their own terminal; it asks for confirmation and
refuses to run without a terminal:

```bash
grillspec gate pause
```

The pause covers the active change in its current phase. It ends by itself at the
next approval or when another change becomes active; `grillspec gate resume` ends it
early. The gate blocks the agent's own `grillspec gate pause`, however it is quoted.

## Per harness

| Harness | Hook | Notes |
|---|---|---|
| Claude Code | `PreToolUse` on `Write`, `Edit`, `MultiEdit`, `NotebookEdit`, `Bash`, `PowerShell` | Hooks run once the workspace is trusted. |
| Codex | `PreToolUse` on `apply_patch`, `Bash` and `exec_command` | Approve the plugin's hooks with `/hooks` after installing, and again after every plugin update; until then they do not run. |
| Cursor | `preToolUse` on `Write`, `Delete`, `Shell` | Hooks run in trusted workspaces. |
| Antigravity | `PreToolUse` on `write_to_file`, `replace_file_content`, `multi_replace_file_content`, `run_command` | Verified with the `agy` CLI 1.4.2. "No opinion" is an empty reply, never `allow`, which some Antigravity versions treat as approving the call for you. The IDE is not smoke-tested yet. |
| GigaCode | none | GigaCode's hooks are experimental and off by default; the skills are the gate there. |

Every hook fails open: if Python is missing or anything goes wrong, the tool call runs.
