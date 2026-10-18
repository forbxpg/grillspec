# grillspec

**Spec-driven agentic development: the agent asks before it guesses.**

`0.1.1` · [Русская версия](README.ru.md)

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

## Support

| Harness | Status | Verified |
|---|---|---|
| Claude Code | supported | session start and phase gate pass smoke runs |
| Cursor | supported | session start and phase gate pass smoke runs (`cursor-agent`) |
| Codex | unverified | hooks need `/hooks` approval after each plugin update |
| Antigravity | supported | session start and phase gate pass smoke runs (`agy` CLI); the IDE is unverified |
| GigaCode | experimental | no hooks; the skills are the gate |

## Data and privacy

grillspec collects no personal data and runs no service of its own: its CLI and hooks
work on files in your project. One feature sends data elsewhere — the **council**.
When a grilling session uses it (`council.enabled` is `ask` by default, so you are
asked each time), the question and its context go as a prompt to the agent CLIs
installed and logged in on your machine (`claude`, `codex`, `cursor-agent`, `gemini`,
`agy`, `gigacode`), under your own accounts with those vendors. Set
`council.external = "never"` to keep the council to local subagents. See
[How the council works](docs/en/how-it-works/council.md).

## Documentation

- English: [docs/en](docs/en/README.md) — why each mechanism exists and how it works
- Русский: [docs/ru](docs/ru/README.md)
- Token costs: [docs/en/tokens.md](docs/en/tokens.md) — about 2,100 tokens per session
  in Claude Code (measured), plus your project's memory block; the rest only when a
  skill is used

## Status

0.1.0, the first public release: grilling, council, specs, memory, plans, execution,
archiving and phase gates. 0.x versions may still change formats; the changelog says
when. See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE). grillspec builds on Superpowers, OpenSpec,
mattpocock/skills and claude-council; see [NOTICE](NOTICE).
