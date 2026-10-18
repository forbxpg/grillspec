# grillspec

**Spec-driven agentic development: the agent asks before it guesses.**

`pre-alpha` · [Русская версия](README.ru.md)

grillspec is a library of agent skills and hooks. Before an agent builds something
that involves a decision, it grills you — one decision at a time, each with a
recommended answer, optionally with a council of independent perspectives — until
nothing is left to guess. Then it writes the spec, extracts what is worth
remembering, writes a plan, and executes it with test-driven development and review.

`grill → spec (+ memory) → plan → execute → archive`

It works in **Claude Code, Cursor, Codex, Antigravity and GigaCode**, on Linux, macOS
and Windows, and needs Python 3.11–3.15 (found automatically) for its hooks and CLI. Specs are written either OpenSpec-compatible
(living specs plus change deltas) or Superpowers-style (one design doc and one plan
per change); you choose per project.

## Install

| Harness | Command |
|---|---|
| Claude Code | `claude plugin marketplace add forbxpg/grillspec && claude plugin install grillspec@grillspec` |
| Codex | `codex plugin marketplace add forbxpg/grillspec`, then `/plugins` |
| Cursor | `/add-plugin forbxpg/grillspec` |
| Antigravity | `agy plugin install https://github.com/forbxpg/grillspec` |
| GigaCode | `uvx grillspec install --harness gigacode` |

Any harness without its plugin system: `uvx grillspec install --harness <name> --copy`.
Then, in your project, ask the agent to "set up grillspec".

## Documentation

- English: [docs/en](docs/en/README.md) — why each mechanism exists and how it works
- Русский: [docs/ru](docs/ru/README.md)
- Token costs: [docs/en/tokens.md](docs/en/tokens.md) — about 2,100 tokens per session
  (measured), the rest only when a skill is used

## Status

Pre-alpha: grilling, council, specs, memory, plans, execution, archiving and phase
gates are in place; release hardening (pressure tests, smoke runs on every harness)
comes next. See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE). grillspec builds on Superpowers, OpenSpec,
mattpocock/skills and claude-council; see [NOTICE](NOTICE).
