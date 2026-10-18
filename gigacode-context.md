# grillspec in GigaCode

grillspec CLI: sh "<this folder>/scripts/grillspec" <command>

`<this folder>` is the directory of this file. Its path, relative to the directory
GigaCode started in (where your shell commands run), is in the `Context from:` line
above. On Windows run `"<this folder>\scripts\grillspec.cmd" <command>` instead. Run
`<that command> status` for the phase of this working tree before any grillspec step.

Phase gates need GigaCode hooks, which are off unless `"hooksConfig": {"enabled": true}`
is in `~/.gigacode/settings.json`. Without them the skills are the only gate: never edit
code while the active change is in `grill`, `spec` or `plan`.
