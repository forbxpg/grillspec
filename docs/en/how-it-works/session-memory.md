# How session memory works

A new session should know where the last one stopped without you explaining it again.
grillspec keeps a small journal per project and hands every new session a short
**resume brief** from it.

## What goes in

| Entry | Written by | When |
|---|---|---|
| `event` | the grillspec CLI, automatically | a change starts, an approval is recorded, a plan task passes `exec done`, a change is archived |
| `handoff` | the agent | before a session ends: what is done, what is next, what is open |
| `discovery` | the agent | the moment it learns something worth keeping |
| `blocker`, `todo` | the agent | when something stops the work, or is left for later |

The agent writes notes with one command, one line each:

```bash
grillspec note handoff -- "done: spec draft; next: approve it; open: retry cap 3 or 5?"
grillspec note discovery -- "receivers answer 502 under burst load"
```

There is no second language model summarising your tool calls: notes come from the
agent that did the work, events from grillspec itself. That costs nothing extra, works
offline and works in every harness — GigaCode on a machine with no internet included.

## What a new session sees

The brief is at most 1,500 estimated tokens: the active change and its phase, then
pinned entries, the latest handoff, open blockers and todos, and the most recent
events. Entries that do not fit are left out whole, never cut. Claude Code, Cursor,
Codex and Antigravity get it at session start; in GigaCode the agent runs
`grillspec recall --brief` once. Everything else is a search away:

```bash
grillspec recall retry backo         # ranked search; words match their beginnings
grillspec recall --pin 12             # always show #12 in the brief
grillspec recall --resolve 9          # blocker #9 no longer stands
grillspec recall --forget 7           # delete #7 for good
```

Search ignores case and accents and treats ё as е. A git worktree of the project (an
execution worktree, say) writes to the main working tree's journal.

## The viewer

`grillspec ui` opens a page in your browser with the timeline grouped by session, the
changes and their phases, search, and buttons to pin, resolve and delete. It runs on 127.0.0.1
while the terminal is open, needs the token from the link it prints for every request,
and loads nothing from the network. Ctrl+C stops it.

## Where it lives, and privacy

The journal is `.grillspec/journal/memory.db` (SQLite) in your project. That folder
ignores itself in git, so the journal stays on this machine and is never committed.
Durable facts for the whole team still belong in the memory block in `AGENTS.md` (see
[How memory works](memory.md)).

Before anything is stored, `<private>…</private>` text is dropped and secrets — API
keys and tokens, bearer, Basic and JWT tokens, passwords in URLs, private keys,
`password=`-style values — become
`<redacted>`. Command output and file contents are never stored, and nothing is sent
anywhere. These rules have no off switch. Nothing is deleted automatically either: the
brief keeps to recent and pinned entries, and old ones stay searchable.
