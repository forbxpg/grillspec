# Plan format

The same text works as a grillspec plan and as an OpenSpec `tasks.md`: OpenSpec reads
the checkbox lines and ignores the rest.

````markdown
# 2026-10-17-rate-limits — plan

## Goal

One sentence: what this builds.

## Architecture

Two or three sentences: the approach.

**Spec:** docs/grillspec/specs/2026-10-17-rate-limits.md

## Global Constraints

- Project-wide rules copied verbatim from the spec, one per line.

## Review Focus

1. An input or failure mode the spec implies but no task's test exercises → the
   expected behaviour (task 1.2 pins it).

## 1. Limiter

- [ ] 1.1 Burst limit — verify: uv run pytest tests/test_limit.py passes

Covers: RL-1, RL-2 · Test: scenario-first

Files: create src/limit.py; test tests/test_limit.py

Interfaces:
- Produces: `allow(receiver: str, now: float) -> bool` in src/limit.py

1. Write `test_eleventh_delivery_rejected` (11 deliveries within 1 s → the eleventh
   is refused) and `test_ten_allowed`. Run them. Expected: FAIL (ImportError).
2. Implement `allow` with a per-receiver sliding window of 1 s and a limit of 10.
3. Run `uv run pytest -q`. Expected: PASS.
4. Commit `feat(limit): per-receiver burst limit`.

## 2. Wiring

- [ ] 2.1 Use the limiter in the sender — verify: uv run pytest -q passes

Covers: — · Test: none: glue; behaviour is covered by 1.1

Files: modify src/sender.py

Interfaces:
- Consumes: `allow(receiver, now)` (1.1)

1. Call `allow` before each delivery; on False, raise `RateLimited`.
2. Run `uv run pytest -q`. Expected: PASS.
````

Rules `grillspec validate` enforces:

- Every checkbox line is `- [ ] N.M <title> — verify: <how>` at column 0, outside code
  blocks, under `## N.`, numbered 1, 2, … within its group.
- Every task has `Test:` (a known strategy) and `Files:`.
- `Covers:` names scenario IDs that exist in the spec (or `—`).
- Every spec scenario is covered by a task whose Test is not `none`.
- No `TBD` / `TODO`; a `**Spec:**` line is present.
- Warnings: more than 12 tasks, more than 8 steps in a task, a plan over 3× the
  spec's length.
