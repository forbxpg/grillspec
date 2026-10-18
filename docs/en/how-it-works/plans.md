# How plans work

After the spec is approved, the agent writes the implementation plan with the
`grillspec-plans` skill. The plan carries every decision an implementer could not make
alone — which files, which names and signatures, which tests prove each task — and
nothing they could.

## The format

One format for both backends. Superpowers keeps it in
`docs/grillspec/plans/<id>.md`; OpenSpec in `openspec/changes/<id>/tasks.md`, where it
is a valid OpenSpec task list: OpenSpec reads the checkbox lines and ignores the rest.

```markdown
## 1. Limiter

- [ ] 1.1 Burst limit — verify: uv run pytest tests/test_limit.py passes

Covers: RL-1, RL-2 · Test: scenario-first

Files: create src/limit.py; test tests/test_limit.py

Interfaces:
- Produces: allow(receiver: str, now: float) -> bool

1. Write test_eleventh_delivery_rejected. Expected: FAIL
2. Implement allow with a 1 s window and a limit of 10.
3. Run uv run pytest -q. Expected: PASS
```

- Groups are `## N. <name>`; each task is **one** checkbox, `- [ ] N.M <title> —
  verify: <how>`. Steps are a plain numbered list, never checkboxes, so grillspec and
  OpenSpec count the same tasks.
- `Covers:` names the spec's scenario IDs; `Files:` and `Interfaces:` say what the
  task touches and what it hands to later tasks.
- Before the groups, a header: Goal, Architecture, `**Spec:**`, Global Constraints and
  Review Focus (up to five failure modes no task's test exercises).

## Test strategies

| `Test:` | Means |
|---|---|
| `scenario-first` | the scenario's test is written and seen failing, then passing |
| `reproduce-first` | a bug is reproduced by a failing test before the fix |
| `characterization` | tests pin current behaviour before a refactor |
| `none: <reason>` | glue or prose with nothing a test could prove |

Every scenario in the spec must be covered by a task whose strategy is not `none`.

## What `grillspec validate` checks

| Rule | Level | What it means |
|---|---|---|
| `plan-checkbox` | error | A checkbox that is not a task line (inside a code block, indented, unnumbered, or without `— verify:`). OpenSpec would count it as a task. |
| `plan-numbering` | error | Task numbers do not run N.1, N.2, … under `## N.` |
| `plan-test` | error | A task has no `Test:` or an unknown strategy. |
| `plan-files` | error | A task has no `Files:` line. |
| `plan-covers-unknown` | error | `Covers:` names a scenario the spec does not have. |
| `plan-coverage` | error | A spec scenario no tested task covers. |
| `plan-tbd` | error | `TBD` or `TODO` left in the plan. |
| `plan-spec-link` | error | No `**Spec:**` line. |
| `plan-size` | warning | More than 12 tasks: consider splitting the change. |
| `plan-steps` | warning | A task with more than 8 steps. |
| `plan-proportion` | warning | The plan is over 3× the spec's length: it may be transcribing code. |

At deep depth, a fresh subagent also reads the spec and the plan and reports where it
would have to guess.

## Approval and edits after it

`grillspec approve plan` refuses when the spec is not approved or changed, when the
plan has errors, or, on the first approval, when a task is already ticked. It records the date and a
fingerprint (`plan_hash`) that ignores which boxes are ticked, so execution never
invalidates it.

If the plan changes after approval:

- **before any task is ticked**, the change goes back to the `plan` phase until you
  approve it again;
- **once execution has started**, status warns `plan changed after approval`, and the
  change is not reported as done — deleting the open tasks cannot finish it — until
  you approve the edited plan again (`grillspec approve plan`; the ticks stay).

## Choosing the executor

After you approve the plan, the agent asks how to execute it and recommends one:

| Executor | How |
|---|---|
| `subagent` | a fresh implementer and a fresh reviewer for every task — most thorough |
| `inline` | the agent executes every task itself, then one fresh reviewer checks the whole branch — cheapest |

The choice is stored with the approval (`--executor`). When that executor's skill is
installed, status names it (`execute the plan with <skill>`); otherwise it says
`execute the plan` (see [How execution works](execution.md)).
