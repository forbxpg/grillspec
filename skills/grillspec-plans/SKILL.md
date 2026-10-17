---
name: grillspec-plans
description: Use when a change's spec is approved and the phase is plan - to write the implementation plan in grillspec's task format (valid as an OpenSpec tasks.md), check it with grillspec validate, get the user's approval and executor choice, and hand off to execution.
---

# Write the implementation plan

Write the plan for an engineer who has never seen this code or this spec. They write
good code once they know the exact interface and the exact test; what they cannot
know is what was decided. The plan carries those decisions and nothing else.

`grillspec` below means the command on the `grillspec CLI:` line of your
session-start context (or `uvx grillspec`).

## 1. Read

Read the approved spec (requirements and scenario IDs) and its decision log. Read the
code the change touches.

## 2. Map the files

List the files to create or modify and what each is responsible for. Prefer small,
focused files; follow the codebase's existing patterns.

## 3. Size the tasks

A task is the smallest unit that carries its own test cycle and that a reviewer could
reject on its own. Fold setup, configuration and docs into the task whose deliverable
needs them.

## 4. Write

Use the format in `references/plan.md`. Superpowers: `docs/grillspec/plans/<id>.md`;
OpenSpec: `openspec/changes/<id>/tasks.md`. In short:

- A header (Goal, Architecture, `**Spec:**`, Global Constraints, Review Focus), then
  groups `## N. <name>`.
- **Each task is one checkbox:** `- [ ] N.M <title> — verify: <how>`. Only tasks are
  checkboxes: never put a box in a step, a code block or an indented list.
- Under it, as plain lines: `Covers: <scenario IDs>` and `Test: <strategy>`,
  `Files:`, `Interfaces:` (what it consumes from earlier tasks and produces for later
  ones, with exact signatures), then numbered steps, each with `Expected:` where
  something runs.
- `Test:` is one of:
  - `scenario-first` — the scenario's test fails first, then passes;
  - `reproduce-first` — a bug reproduced by a failing test;
  - `characterization` — tests pin existing behaviour before a refactor;
  - `none: <reason>` — glue or prose with nothing a test could prove.
- Every scenario in the spec is covered by a task whose Test is not `none`.

What a step contains: a test step names the test and its assertions with the spec's
exact values; a code step gives the signature, the file and the values the spec pins;
a verification step gives the command and the output that means it passed. No
function bodies the signature and tests already determine; no lines that decide
nothing (`TBD`, "handle edge cases", "add validation").

## 5. Self-review

- Every requirement and scenario has a task.
- Every step lets the implementer write exactly one reasonable thing.
- Names and signatures match across tasks.
- Review Focus lists up to five failure modes the spec implies but no test exercises,
  each pinned by a test in the task that owns the code (or "none found").
- The plan is not several times longer than the spec: if code blocks dominate, it is
  transcribing the program.

At deep depth, also dispatch one fresh subagent with `references/plan-check.md`, the
spec and the plan only. Fix what facts settle; put decisions to the user.

## 6. Validate

Run `grillspec validate` until there are no errors. Read the `plan-*` warnings: too
many tasks or steps, or a plan out of proportion, usually mean the change should be
split or the plan is writing code.

## 7. Review and choose the executor

Show an overview: the plan file, the groups and tasks with their Covers and Test, and
the Review Focus. Ask: "Do you approve this plan?" Only an explicit yes counts.

Then ask how to execute it, with a recommendation:

- **subagent-driven**: a fresh implementer and a fresh reviewer per task. Most
  thorough; recommend it when tasks depend on each other's interfaces or a mistake
  would be costly.
- **inline**: you execute every task in this session, then one fresh reviewer checks
  the whole branch. Cheapest; recommend it for small, independent tasks.

## 8. Approve and hand off

1. Run `grillspec approve plan --executor <subagent|inline>`. It refuses an invalid
   plan, a spec that changed since approval, or, on the first approval, a ticked box.
2. Name the plan file and suggest committing it; never commit yourself.
3. Continue with `grillspec-subagent-execution` or `grillspec-inline-execution`. If it
   is not installed, say so: the phase is `execute`, and the plan can be followed by
   hand. Stop.

Editing the plan after approval sends the change back to the plan phase until it is
approved again; once a task is ticked, status only warns, and a changed plan is never
reported as done until the user approves the edit (`grillspec approve plan` again; the
ticks stay).

## Red flags

| Thought | Reality |
|---|---|
| "I'll put checkboxes on the steps for tracking." | OpenSpec counts every box as a task. Only tasks are boxes. |
| "This scenario is covered by the glue task." | A `Test: none` task covers nothing. Give the scenario a tested task. |
| "I'll write the function body so it's clear." | The signature and the test decide the body. Writing it is transcribing. |
| "Details later, TBD." | A plan line that decides nothing is a guess deferred to the executor. |
| "They approved the spec, so the plan is approved." | The plan needs its own explicit yes. |
