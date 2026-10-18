# What grillspec costs in tokens

Everything grillspec puts into an agent's context is either **always on** — paid in
every session — or **on demand** — paid only when a skill is used. Skills are written
in English because non-English text costs more tokens on every activation; these docs
are never loaded into an agent, so having them in two languages costs nothing.

## Estimates

`grillspec tokens` estimates each part from its UTF-8 size: bytes ÷ 4.5, rounded up.
The ratio is calibrated against a measured session (below). The table is generated;
CI fails when it falls behind the skills.

<!-- grillspec:tokens:begin -->
| Part | When it is loaded | ≈ tokens |
|---|---|---|
| router and status line | every session (hook harnesses) | 1,249 |
| skill catalogue (18 skills) | every session | 844 |
| `grillspec-archive` | when the skill is used | 490 |
| `grillspec-council` | when the skill is used | 1,135 (+168 in references) |
| `grillspec-debugging` | when the skill is used | 2,103 (+2,842 in references) |
| `grillspec-finishing` | when the skill is used | 1,741 |
| `grillspec-grill` | when the skill is used | 1,436 |
| `grillspec-init` | when the skill is used | 362 |
| `grillspec-inline-execution` | when the skill is used | 4,704 |
| `grillspec-memory` | when the skill is used | 912 |
| `grillspec-parallel-agents` | when the skill is used | 1,315 |
| `grillspec-plans` | when the skill is used | 1,132 (+630 in references) |
| `grillspec-receiving-review` | when the skill is used | 1,315 |
| `grillspec-requesting-review` | when the skill is used | 625 (+1,434 in references) |
| `grillspec-specs` | when the skill is used | 1,012 (+913 in references) |
| `grillspec-subagent-execution` | when the skill is used | 7,477 (+4,516 in references) |
| `grillspec-tdd` | when the skill is used | 2,426 (+1,831 in references) |
| `grillspec-verification` | when the skill is used | 762 |
| `grillspec-worktrees` | when the skill is used | 1,487 |
| `using-grillspec` | when the skill is used | 1,229 (+773 in references) |
<!-- grillspec:tokens:end -->

A skill's references are the other files in its folder; the agent reads them only
when the skill points it there. Your project's memory block in `AGENTS.md` is always
on as well: `grillspec tokens --project` adds it.

## Measured

`tests/benchmark/overhead.sh claude` runs a trivial prompt in an empty repository with
and without grillspec and subtracts the input tokens the harness reports
(`input + cache creation + cache read`).

| Date | Harness | Without | With | Overhead |
|---|---|---|---|---|
| 2026-10-18 | Claude Code 2.1.287 | 45,373 | 47,469 | 2,096 |

The overhead is the router, the status line and the skill catalogue; it matches the
estimate within a few tokens.

## Refreshing

- After changing a skill: `uv run python scripts/check_tokens.py --write`.
- After a harness or model update: run the benchmark and add a row.
