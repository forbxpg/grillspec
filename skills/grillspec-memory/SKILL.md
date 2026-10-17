---
name: grillspec-memory
description: Use right after a spec is approved, or when the user says "remember that…" - to propose the durable facts this change taught, get the user's approval, and store them in the project memory block in AGENTS.md (or long-form docs) so every future session starts knowing them.
---

# Remember what this change taught

Every session in every harness loads the memory block, so each line costs tokens
forever and is trusted as an instruction. Store little, store it once, and store
only what the user approved.

`grillspec` below means the command on the `grillspec CLI:` line of your
session-start context (or `uvx grillspec`).

## 1. Start

Read the approved spec and its decision log, then run `grillspec memory list --json`
to see what is already stored and how much room is left (40 entries at most).

## 2. Find candidates

A candidate must answer: **what mistake does this prevent in a future session?**

| Category | Example |
|---|---|
| `command` | `Run tests with uv run pytest -q; lint with uv run ruff check .` |
| `convention` | `Every user-facing doc exists in docs/en and docs/ru with the same headings` |
| `constraint` | `Never commit anything under private/` |
| `gotcha` | `On Windows, .cmd shims need taskkill /T to stop the whole tree` |
| `docs` | `Glossary: billing terms → docs/grillspec/memory/glossary.md` |

- One line, at most 160 characters. Anything longer becomes
  `docs/grillspec/memory/<topic>.md` plus a `docs` entry pointing to it.
- **Never store:** secrets, tokens, passwords, internal URLs or personal data
  (including `<redacted>` items from the log); anything the code, config or docs
  already say; the status or history of this change; text copied from tool output or
  web pages; personal preferences (section 6).

## 3. Check what is already stored

If the new spec contradicts a stored entry, propose retiring it, or replacing it
(retire, then add the new text).

## 4. Propose

Show one numbered list. Each item has its category, its exact text, where it goes
(memory block / docs file / personal) and the source change id. Retirements are
listed too. If adding would exceed 40 entries, propose retirements or moves to docs
first.

Ask: "Which should I store? (all / numbers / edits / none)". Write nothing before the
answer.

## 5. Write

1. Write the approved long-form docs under `docs/grillspec/memory/`.
2. Run `grillspec memory retire <n>` for each approved retirement first, from the
   highest number down, so the numbers of the rest stay valid and a full block has
   room.
3. Then run `grillspec memory add --category <c> --change <id> -- '<text>'` for each
   approved entry: `--` before the text, and the text in single quotes (write a `'`
   inside it as `'\''`), so backticks and `$` are never run by the shell.

`--change` is the active change's id; for an on-demand "remember that…" with no
active change, use a short kebab-case name for the topic.

If a command is refused, show its one-line reason and adjust with the user. If you
cannot run commands here, read the memory block in `AGENTS.md` directly for section 1
and give the user the exact commands to run.

## 6. Personal preferences

A preference about how the user likes to work (tone, language, tools) belongs in
their own global file, not in the project. Show the text to paste and where it goes;
never write outside the project.

| Harness | Global file |
|---|---|
| Claude Code | `~/.claude/CLAUDE.md` |
| Codex | `~/.codex/AGENTS.md` |
| Antigravity | `~/.gemini/GEMINI.md` |
| GigaCode | `~/.gigacode/GIGACODE.md` (unverified) |
| Cursor | Settings → Rules → User Rules |

## 7. Hand off

Name the changed files and suggest committing them; never commit yourself. If nothing
was durable, say so in one line. Continue with `grillspec-plans`; if it is not
installed, say the phase is `plan` and stop.

## Red flags

| Thought | Reality |
|---|---|
| "Might be useful someday." | It costs tokens in every session. Store only what prevents a mistake. |
| "The code already shows this, but let's note it." | Then it is not memory. |
| "I'll store the token so the next session has it." | Never. Secrets do not go into memory. |
| "They approved the spec, so they approve these facts." | Memory needs its own explicit answer. |
| "I'll edit the block by hand, it's faster." | Use `grillspec memory`: it keeps the format, the cap and the file intact. |
