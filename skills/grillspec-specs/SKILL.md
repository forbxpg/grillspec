---
name: grillspec-specs
description: Use when a grill is confirmed and the change is in the spec phase - to turn the decision log into a spec with requirements and ID-tagged scenarios, check it with grillspec validate and a builder-check, and get the user's approval before any plan or code.
---

# Write the spec from the decision log

The decision log says why; the spec says what the system shall do, in requirements
and scenarios the plan and the tests will cite. Write only what the log decided:
a requirement with no decision behind it is a guess.

`grillspec` below means the command on the `grillspec CLI:` line of your
session-start context (or `uvx grillspec`).

## 1. Start

Read the status line (or `grillspec status --json`): phase `spec`, the change id and
`log=`. Read the whole log. Read the backend template: `references/superpowers.md` or
`references/openspec.md`.

## 2. Triage deferred items

For every open item marked `deferred`:

- **It changes a requirement, the approach or the work split** → it cannot wait. Ask
  it now, the way the grill asks (recommendation first, trade-offs, reversibility),
  and log the answer under Settled.
- **It does not** → list it under `## Open questions` with its log ID, your
  recommendation and when it must be decided (before the plan, or during execution).

## 3. Pick the scenario ID tag

Choose 2-4 capital letters for this change (`RL` for rate limits). Grep
`openspec/specs` and the other changes for `Scenario: <TAG>-` to make sure the tag is
free. Number scenarios `RL-1`, `RL-2`, … and never renumber: plans and tests cite
these IDs. A MODIFIED requirement keeps the IDs its scenarios already have.

## 4. Write

Follow the template for the backend.

- Every requirement traces to a Settled decision. Never invent one to fill a gap or to
  satisfy the validator.
- A requirement states behaviour with SHALL or MUST; each scenario is one observable
  case with `- **WHEN**` and `- **THEN**` lines. Describe what a user or another
  system sees, not classes, files or libraries.
- SHALL, MUST, WHEN, THEN and the section headers stay English; everything else uses
  the project's artifact language.
- Never edit Settled lines of the log. Add the new sections with targeted edits
  (Edit, or your harness's equivalent); never rewrite a file that holds the log, so
  the log stays exactly as the grill left it.
- OpenSpec: read `openspec/specs/` before choosing capabilities. MODIFIED copies the
  whole living requirement block and then edits it. A change with no behaviour change
  (refactor, docs, tooling) sets `skip_specs: true` instead of inventing a delta.

## 5. Validate

Run `grillspec validate`. Fix every error and run it again until it reports 0 errors.
Read the warnings; fix them when they point at a real problem.

## 6. Builder-check (standard and deep)

Dispatch one fresh subagent with the prompt in `references/builder-check.md`, the log
and the spec files, and nothing else. It returns at most 10 findings and edits
nothing.

- A finding you can settle from facts: fix the spec.
- A finding that needs a decision: put it to the user as a grill question and log it.
- After fixes, at most one re-check, then `grillspec validate` again.

No subagent tool in this harness: run the same checklist yourself and say the check
was done by the author, so it is weaker. Quick depth: skip this step.

## 7. Review

Show an overview, not the whole text:

- the spec files;
- each requirement with its number of scenarios;
- what the builder-check found and how each finding was resolved;
- the open questions, if any: approving means approving with them open.

Ask: "Do you approve this spec?" Only an explicit yes counts. On changes: edit, run
`grillspec validate`, and ask again.

## 8. Approve and hand off

1. Run `grillspec approve spec`. It runs the validator and refuses on errors.
2. Name the spec files and suggest committing them; never commit yourself.
3. Continue with `grillspec-memory`; if it is not installed, with `grillspec-plans`;
   if neither is, say the phase is now `plan` and stop.

Editing the spec after approval sends the change back to the spec phase until it is
approved again (once the plan is approved, status only warns).

## Red flags

| Thought | Reality |
|---|---|
| "This requirement is obvious, no decision needed." | Then it is a guess. Find the decision or ask. |
| "I'll add a requirement just in case." | Unasked scope. Leave it out or ask. |
| "Nicer to renumber the IDs." | Plans and tests cite them. IDs never change. |
| "The deferred item can wait." | Only if it changes no requirement. Check before writing. |
| "The validator is green, so it's done." | Structure is not meaning. Run the builder-check and the review. |
| "They approved the grill, so the spec is approved." | Each approval needs its own explicit yes. |
