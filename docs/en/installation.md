# Installation

grillspec needs **Python 3.11 or newer** (3.11 to 3.15) on the machine where the agent
runs: its hooks and its CLI are Python, standard library only. Without it, grillspec
still installs and its skills still load, but the hooks report "gates are OFF" instead
of the session status (see [How the bootstrap works](how-it-works/bootstrap.md)).

## Which Python is used

Machines often have several Pythons, and `python3` is not always the newest one — or,
on Windows, not a real Python at all. grillspec never calls `python3` blindly. Its
launchers (`scripts/grillspec` on Linux and macOS, `scripts/grillspec.cmd` on Windows)
take the first candidate that is 3.11 or newer:

1. the executable in `GRILLSPEC_PYTHON`, if you set it;
2. on Linux and macOS: `python3.15` … `python3.11`, then `python3`, `python`, then the
   `py` launcher (present under Git Bash on Windows);
3. on Windows: `py -3.15` … `py -3.11`, then `python3`, `python`;
4. `uv run --python ">=3.11"`, if `uv` is installed — it downloads a Python when none
   fits.

A machine with only Python 3.14, or with an old `python3` next to a newer `python3.13`,
works without configuration. To pin one: `export GRILLSPEC_PYTHON=/path/to/python`
(PowerShell: `$env:GRILLSPEC_PYTHON = "C:\Path\To\python.exe"`).

## Per harness

| Harness | Install | Update |
|---|---|---|
| Claude Code | `claude plugin marketplace add forbxpg/grillspec`, then `claude plugin install grillspec@grillspec` | `claude plugin update grillspec@grillspec` |
| Codex | `codex plugin marketplace add forbxpg/grillspec`, then pick grillspec in `/plugins`; trust its hooks in `/hooks` | `/plugins` |
| Cursor | `/add-plugin forbxpg/grillspec` | Cursor's plugin manager |
| Antigravity | `agy plugin install https://github.com/forbxpg/grillspec` | run the install again |
| GigaCode | `gigacode extensions link /path/to/grillspec` (see [GigaCode](#gigacode)) | replace the folder's contents |

Codex runs plugin hooks only after you trust them in `/hooks`. Until then the router
still loads from its skill description; you only miss the status line.

## Without npx or uv

None of the installs below needs npx, npm or uv. To get grillspec onto a machine that has
only Python and git (or neither), use any of these and keep the folder where it is:

```bash
git clone https://github.com/forbxpg/grillspec
# or: download a release's source zip from https://github.com/forbxpg/grillspec/releases and unzip it
# or, from a PyPI mirror (the source distribution carries the whole plugin):
python -m pip download grillspec --no-deps --no-binary :all: && tar -xzf grillspec-*.tar.gz
```

Run the CLI from that folder with its launcher, which finds Python 3.11+ by itself:
`sh scripts/grillspec <command>` on Linux and macOS, `scripts\grillspec.cmd <command>`
on Windows. Or install it as a command: `python -m pip install grillspec`, then
`grillspec <command>`.

## GigaCode

grillspec is a native GigaCode extension (`gigacode-extension.json`). GigaCode installs
extensions only from a local folder, with nothing but its own binary:

```bash
gigacode extensions link /path/to/grillspec     # answer Y
```

- Every session then loads the router and a line that tells the agent how to run the
  grillspec CLI from that folder; the 18 skills appear in `/skills`.
- Use `link`, not `install`: `install` sees `.claude-plugin/` in the folder, installs it
  as a Claude plugin and drops both the router and the gates.
- Phase gates need GigaCode hooks, which are off by default. Turn them on in
  `~/.gigacode/settings.json`:

  ```json
  { "hooksConfig": { "enabled": true } }
  ```

  (or start GigaCode with `--experimental-hooks`). Without hooks the skills are the only
  gate.
- Update: replace the folder's contents (`git pull`, or unpack a newer release in its
  place); GigaCode's corporate mode disables `extensions update`. Remove:
  `gigacode extensions uninstall grillspec`.

Checked against the GigaCode 0.13.1 bundle: `link` loads both context files and all 18
skills. A live session, which needs a GigaCode licence, has not been run yet.

## Without a plugin system

The fallback installer copies the skills into the harness's skill directory and
records every file it wrote:

```bash
grillspec install --harness gigacode                 # project: .gigacode/skills
grillspec install --harness codex --copy --scope user  # user: ~/.agents/skills
grillspec install --harness gigacode --dry-run       # list writes, change nothing
```

(`grillspec` here is any of the ways above: the launcher, `pip install`, or `uvx`.)
For harnesses that have plugins, `install` prints the native command unless you pass
`--copy`. For GigaCode it also adds one import line to `GIGACODE.md`, so the router
loads in every session; prefer the extension, because GigaCode reads project skills
only when it starts in the project's root.

## Uninstall

```bash
grillspec uninstall --harness gigacode
```

`uninstall` removes exactly the files and the import line that `install` recorded in
`.grillspec/install-receipt.json` (or the user-level receipt next to your user config).
Edits you made to `GIGACODE.md` stay.

## Set up a project

Ask the agent to "set up grillspec in this repo". The `grillspec-init` skill recommends a spec
backend, shows every change to your files, and writes only after you say yes. The same
from the shell:

```bash
grillspec detect
grillspec init --backend openspec --dry-run
grillspec init --backend openspec
```
