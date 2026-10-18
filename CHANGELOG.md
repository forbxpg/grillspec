# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html); while on 0.x, a minor
release may break things and says so here.

## [Unreleased]

## [0.1.1] - 2026-10-18

### Added

- Plugin icon for the Claude plugin directory.
- README section on data and privacy: what the council sends to external agent CLIs
  and how to turn it off.

### Changed

- Antigravity: the phase gate is on. Its "no opinion" answer is now an empty reply
  instead of `{"decision": "allow"}`, which some Antigravity versions treat as approval;
  verified with `agy` 1.4.2.
- `grillspec-subagent-execution` keeps its process diagram, fix loop and example in
  reference files, so its body stays under Antigravity's 24 KB skill limit.

## [0.1.0] - 2026-10-18

First public release.

### Added

- `grillspec` CLI (`status`, `use`, `init`, `detect`, `install`, `uninstall`, `hook`,
  `version`), standard library only, Python 3.11+.
- Layered configuration: project `.grillspec/config.toml` over the user file over
  built-in defaults.
- Phases derived from artifacts and approvals; one active change per working tree.
- Session-start bootstrap for Claude Code, Cursor, Codex and Antigravity through one
  fail-open hook runner; GigaCode bootstraps through `GIGACODE.md`.
- `using-grillspec` router skill and `grillspec-init` skill.
- Plugin manifests for Claude Code, Cursor, Codex and Antigravity; a fallback installer
  with an exact uninstall.
- Grilling: `grillspec new`, decision logs, depth settings and the `grillspec-grill`
  skill.
- Council: `grillspec council ask` with role subagents and external agent CLIs.
- Specs: `grillspec validate` for both backends, scenario IDs, content-bound
  `grillspec approve spec`.
- Memory: a managed block in `AGENTS.md` and `grillspec memory list|add|retire`.
- Plans: one plan format for both backends, plan validation and `approve plan`.
- Execution: `grillspec exec` helpers and execution skills adapted from Superpowers.
- Archive: `grillspec archive` merges OpenSpec deltas or marks superpowers changes.
- Phase gates: pre-tool hooks block code edits while a change is grilled, specced or
  planned; `grillspec gate pause|resume`.
- `grillspec tokens` and a generated cost table in the docs; measured session
  overhead.

[Unreleased]: https://github.com/forbxpg/grillspec/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/forbxpg/grillspec/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/forbxpg/grillspec/releases/tag/v0.1.0
