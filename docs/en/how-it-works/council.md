# How the council works

While grilling, the agent can ask a council for independent views on a decision
before putting it to you. The council informs your choice; it never makes it. Under
the options you see one line with what the members agreed on and who dissented:

```
Council 3/4: A (claude, codex, simplicity) · dissent devil→B: retries hide outages · gemini: timeout
Same-model members agreeing is a weak signal.
```

Only the dissent reaches the decision log (`· council 3/4 · dissent devil→B`), and
the log's metadata counts council runs (`council_calls=`).

## Members

| Member | What it is |
|---|---|
| `role:simplicity` | A subagent on the agent's own model, looking for the smallest option that fully works. |
| `role:devil` | A subagent arguing against the option most people would pick. |
| `role:risk` | A subagent looking for what breaks in production and what is costly to undo. |
| `cli:<vendor>[@<model>]` | Another vendor's agent CLI, called headless by `grillspec council ask`. Without `@<model>` it uses that CLI's own default model. |

Roles run on the same model as the agent, so their agreement is a weak signal; the
agent says so. External members bring other models' blind spots instead.

When the setup question offers a council, it names the members and the cost.

## When it runs

| Depth | Decisions that get a council |
|---|---|
| `quick` | none |
| `standard` | root decisions and hard-to-reverse ones |
| `deep` | every decision |

The council starts as soon as its decision can be asked, and runs in the background
while the agent asks you other questions. Each external member gets
`council.timeout` seconds (120 by default); members that miss it are named in the
question, and the grill goes on without them.

## What each vendor receives

External members get one prompt on stdin and nothing else: the question, its
options, the settled decisions it depends on, and a short summary of facts the
agent wrote, without secrets. The decision sits inside data delimiters with a random
marker per call, so text inside it cannot pose as instructions.

| Member | Receives | Runs in | Tools |
|---|---|---|---|
| role subagent | the same prompt | the agent's session | none needed |
| external CLI | the prompt on stdin | a new empty temporary directory, deleted afterwards | its read-only or planning mode; no tools at all for claude; no MCP servers (claude); no session saved (claude, codex) |
| external CLI with `share_project = true` | the prompt on stdin | the project directory | the same mode, with your project as its working directory |

Read-only is not the same as no access. In their read-only modes codex, cursor-agent,
gemini, agy and gigacode can still read files your user account can read, anywhere on
the machine; the prompt tells them not to, and the empty directory only keeps your
project out of their immediate view. Only `claude` runs with every tool turned off. If
that is not acceptable, set `council.external = "never"` or list only `cli:claude`.

`grillspec council ask --dry-run` prints every command, its directory and the full
prompt without running anything.

## Turning external members off

Set `council.external = "never"` in `.grillspec/config.toml` (for a project) or in
your user config. It wins in either file: a project cannot turn external members
back on for you, and you cannot turn them on for a project that forbids them. Role
members still work.

## Cost

A council run makes one call per member. External calls spend your quota with each
vendor: roughly `<decisions> × <members>` calls per grill, where a standard grill
has about 4 council decisions and a deep one about 15.

## Vendors

`grillspec detect --json` reports, for each CLI, whether it is installed and
logged in. The check never sends a prompt.

| Vendor | Headless call | Login check |
|---|---|---|
| `claude` | `claude -p --tools "" --strict-mcp-config --no-session-persistence --setting-sources user --output-format json` | `claude auth status` |
| `codex` | `codex exec --skip-git-repo-check -s read-only --ephemeral -` | `codex login status` |
| `cursor-agent` | `cursor-agent -p --trust --mode ask --output-format json` | `cursor-agent status --format json` |
| `gemini` | `gemini --approval-mode plan -o json -p "…"` | none: an API key in `GEMINI_API_KEY` or a saved login counts; otherwise unknown |
| `agy` | `agy --sandbox -p "…"` | none: unknown |
| `gigacode` (experimental) | `gigacode --approval-mode plan -o json "…"` | `gigacode auth status` |

A CLI that is logged out is skipped and named in the question. An unknown login
state is tried; a failure shows up as an error.

### GigaCode

GigaCode support is experimental: it is never offered in the setup question and runs
only when you list `cli:gigacode` in `council.members`. The GigaCode CLI needs
Node.js 22 or 24 LTS. On Node 26 it fails with `UND_ERR_INVALID_ARG invalid onError
method` whenever its corporate CA bundle is present.
