# How memory works

After a spec is approved, the agent proposes the durable facts the change taught —
how to run the tests, a convention, a constraint, a pitfall — and stores only the
ones you approve. Every future session in every harness then starts knowing them.

## Where memory lives

In `AGENTS.md`, in its own block:

```markdown
<!-- grillspec:memory:begin -->
## Project memory (grillspec)
- [command] Run tests with uv run pytest -q (2026-10-17-ci)
- [constraint] Never commit anything under private/ (2026-10-17-docs)
<!-- grillspec:memory:end -->
```

`AGENTS.md` is the file all five harnesses load (Claude Code and GigaCode through the
`@AGENTS.md` line that `grillspec init` adds to `CLAUDE.md` and `GIGACODE.md`). The
memory block is separate from the block `grillspec init` manages: re-running `init`,
upgrading grillspec or uninstalling never changes it.

## What is remembered

Each entry must answer one question: what mistake does this prevent in a future
session?

| Category | For |
|---|---|
| `command` | how to build, test or run the project |
| `convention` | naming, style, structure rules |
| `constraint` | invariants and "never do X" rules |
| `gotcha` | non-obvious pitfalls |
| `docs` | a pointer to long material in `docs/grillspec/memory/<topic>.md` (a glossary, background on a decision) |

Never stored: secrets, tokens, passwords, internal URLs or personal data; anything
the code, config or docs already say; the status or history of a change; text copied
from tool output or web pages; personal preferences.

## Size and token cost

At most 40 entries of at most 160 characters each — about 1.6k tokens in the worst
case, paid in every session. When the block is full, the agent proposes retiring
entries or moving them to long-form docs before adding new ones.

## Commands

| Command | What it does |
|---|---|
| `grillspec memory list [--json]` | numbered entries and how many of 40 are used |
| `grillspec memory add --category <c> --change <id> -- '<text>'` | adds one entry; refuses duplicates, malformed text and a 41st entry |
| `grillspec memory retire <n>` | removes entry n |

Writes are atomic, keep the file's permissions and write through a symlinked
`AGENTS.md`; the file is rewritten with its dominant line ending. You can also edit the block by
hand; `grillspec memory` tells you if a line no longer has the entry format.

## Personal preferences

How you like to work (tone, language, tools) belongs in your own global file, not in
the project. The agent shows you the text to paste; it never writes outside the
project.

| Harness | Global file |
|---|---|
| Claude Code | `~/.claude/CLAUDE.md` |
| Codex | `~/.codex/AGENTS.md` |
| Antigravity | `~/.gemini/GEMINI.md` |
| GigaCode | `~/.gigacode/GIGACODE.md` (unverified) |
| Cursor | Settings → Rules → User Rules |

## Keeping memory current

Each entry names the change it came from. When a later spec contradicts an entry, the
agent proposes retiring or replacing it, and does so only after your answer.
