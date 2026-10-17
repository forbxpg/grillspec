# Installation

grillspec needs **Python 3.11 or newer** on the machine where the agent runs: its hooks
and its CLI are Python, standard library only. Without it, grillspec still installs and
its skills still load, but the hooks report "gates are OFF" instead of the session
status (see [How the bootstrap works](how-it-works/bootstrap.md)).

## Per harness

| Harness | Install | Update |
|---|---|---|
| Claude Code | `claude plugin marketplace add forbxpg/grillspec`, then `claude plugin install grillspec@grillspec` | `claude plugin update grillspec@grillspec` |
| Codex | `codex plugin marketplace add forbxpg/grillspec`, then pick grillspec in `/plugins`; trust its hooks in `/hooks` | `/plugins` |
| Cursor | `/add-plugin forbxpg/grillspec` | Cursor's plugin manager |
| Antigravity | `agy plugin install https://github.com/forbxpg/grillspec` | run the install again |
| GigaCode | `uvx grillspec install --harness gigacode` | run the install again |

Codex runs plugin hooks only after you trust them in `/hooks`. Until then the router
still loads from its skill description; you only miss the status line.

## Without a plugin system

The fallback installer copies the skills into the harness's skill directory and
records every file it wrote:

```bash
uvx grillspec install --harness gigacode                 # project: .gigacode/skills
uvx grillspec install --harness codex --copy --scope user  # user: ~/.agents/skills
uvx grillspec install --harness gigacode --dry-run       # list writes, change nothing
```

For harnesses that have plugins, `install` prints the native command unless you pass
`--copy`. For GigaCode it also adds one import line to `GIGACODE.md`, so the router
loads in every session.

## Uninstall

```bash
uvx grillspec uninstall --harness gigacode
```

`uninstall` removes exactly the files and the import line that `install` recorded in
`.grillspec/install-receipt.json` (or the user-level receipt next to your user config).
Edits you made to `GIGACODE.md` stay.

## Set up a project

Ask the agent to "set up grillspec in this repo". The `init` skill recommends a spec
backend, shows every change to your files, and writes only after you say yes. The same
from the shell:

```bash
grillspec detect
grillspec init --backend openspec --dry-run
grillspec init --backend openspec
```
