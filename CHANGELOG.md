# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html); while on 0.x, a minor
release may break things and says so here.

## [Unreleased]

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
