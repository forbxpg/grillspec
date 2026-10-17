# How execution works

Once the plan is approved, the agent executes it task by task with one of two
executors, under test-driven development, and finishes with a review of the whole
branch. These skills are adapted from Superpowers 7.0.0 (see `NOTICE`); grillspec
re-points them to its own plan format and to `grillspec exec`, which works the same on
Linux, macOS and Windows.

## Two executors

| Executor | Skill | How | Recommended when |
|---|---|---|---|
| `subagent` | `grillspec-subagent-execution` | a fresh implementer subagent per task, then a fresh task reviewer, fix rounds until clean; a final whole-branch review | tasks depend on each other's interfaces, or a shipped mistake would be costly |
| `inline` | `grillspec-inline-execution` | the agent implements every task itself, test-first; one fresh reviewer checks the whole branch at the end | tasks are small and independent; also the executor in a harness without subagents |

You pick one when you approve the plan; status then says
`execute the plan with <skill>`.

## The helpers: `grillspec exec`

| Command | What it does |
|---|---|
| `grillspec exec workspace` | creates `.grillspec/exec/<change-id>/` (ignored by git) with the ledger |
| `grillspec exec start <N.M>` | writes the task's brief (the plan header plus that task) and prints BASE, the commit the task starts from |
| `grillspec exec done <N.M> <BASE> -- <test command>` | runs the tests without a shell; only when they pass, ticks the task's box in the plan and adds a line to the ledger |
| `grillspec exec review-package <BASE> [<HEAD>]` | writes the commits, the stat and the diff for a reviewer; refuses an empty or unrelated range |

Because `exec done` ticks the plan's own checkboxes, `grillspec status` and OpenSpec
both see the progress, and a new session resumes at the first unticked task.

## The ledger

`.grillspec/exec/<change-id>/progress.md` records what the session would otherwise
forget: completed tasks with their commit range and test command, every **ruling**
(a decision the agent took when the plan was ambiguous or wrong, with what it costs if
wrong), fix rounds, and deferred review findings. The executor's final message lists
every ruling and deferred finding.

## Test-driven development

Each task's `Test:` line decides its red: `scenario-first` and `reproduce-first` tasks
write all their tests first and watch them fail once, for the right reason, before any
production code; `characterization` tests pin current behaviour before a refactor and
stay green; `none` tasks are glue. Debugging (`grillspec-debugging`) starts from the
root cause, and no task or branch is called done without fresh verification output
(`grillspec-verification`).

## Review and finishing

Reviews follow `grillspec-requesting-review`; the agent weighs feedback with
`grillspec-receiving-review` instead of agreeing by reflex. When every task is ticked
and the final review is clean, `grillspec-finishing` offers the ways to integrate the
branch (merge, pull request, keep it) and cleans up worktrees made with
`grillspec-worktrees`. Commits follow the project's rules in `AGENTS.md`.
