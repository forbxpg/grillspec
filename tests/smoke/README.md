# Harness smoke tests

`smoke.sh <harness>` starts the harness headless in a throwaway git repository and asks
it to repeat the `grillspec:` status line it received at session start. PASS means the
bootstrap reached the agent in that harness.

- `claude` loads the plugin from this checkout with `--plugin-dir`; nothing is installed.
- `codex`, `cursor`, `antigravity` need grillspec installed through their plugin
  systems first (see `docs/en/installation.md`); Codex also needs the hooks trusted.
- `gigacode` is installed into the temp repo by the script itself.

These runs use your own credentials and cost tokens, so they are not part of CI.
Record every run below; unverified harness facts in the umbrella spec are updated from
these results.

## Results

| Date | Harness | Version | Result | Note |
|---|---|---|---|---|
| 2026-10-17 | Claude Code | 2.1.287 (Claude Code) | PASS | |
| 2026-10-17 | Codex | 0.149.1 | not run | CLI present but not authenticated (401) |
| 2026-10-17 | Cursor | — | not run | `cursor-agent` not installed |
| 2026-10-17 | Antigravity | — | not run | `agy` not installed; headless flag `-p` unverified |
| 2026-10-17 | GigaCode | — | not run | `gigacode` not installed; headless flag `-p` unverified |
