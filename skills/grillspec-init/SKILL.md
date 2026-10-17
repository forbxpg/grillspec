---
name: grillspec-init
description: Use when setting grillspec up in a project, when the user asks to install or configure grillspec, or when grillspec status says to run init.
---

# Set grillspec up in a project

Setup touches files the user owns (`AGENTS.md`, `CLAUDE.md`, `GIGACODE.md`,
`.gitignore`), so nothing is written before the user has seen it and said yes.

`grillspec` below means the command on the `grillspec CLI:` line of your session-start
context (the plugin's launcher, which finds a suitable Python on any OS), or
`grillspec` / `uvx grillspec` when installed from PyPI.

1. Run `grillspec detect --json`. Read `signals` and `recommended_backend`.
2. Put the backend choice to the user, recommendation first and marked
   `(Recommended)`, each option with its trade-off:
   - **openspec** — living specs in `openspec/specs/` plus one change folder per
     change, merged in on archive. Fits long-lived and existing codebases.
   - **superpowers** — one dated design doc and one plan per change in
     `docs/grillspec/`. Fits one-off features and new projects.

   Give the reason from the signals: existing source code, an `openspec/`
   directory, or a long git history.
3. Run `grillspec init --backend <choice> --dry-run` and show the user every file it
   lists, with what will be added: the config file, the `.gitignore` line, the
   block between `<!-- grillspec:begin -->` and `<!-- grillspec:end -->` in
   `AGENTS.md`, and the `@AGENTS.md` line in `CLAUDE.md` / `GIGACODE.md`.
4. Ask for an explicit yes. Anything else is a no: change nothing.
5. Run `grillspec init --backend <choice>`, then `grillspec status`, and report both.

If `init` reports unbalanced grillspec markers, show the user the file and ask
them to fix the markers; never repair a user's file by guessing.
