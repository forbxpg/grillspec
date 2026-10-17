# How specs work

After the grill, the agent writes the spec with the `grillspec-specs` skill. The
decision log says why; the spec says what the system shall do, as requirements and
scenarios that the plan and the tests cite.

## From log to spec

1. **Deferred decisions are sorted first.** One that would change a requirement is
   asked right away; any other goes to "Open questions" with a recommendation and a
   deadline.
2. **The agent writes the spec** from the template for your backend. Every
   requirement comes from a decision in the log, never from a guess.
3. **`grillspec validate`** checks the structure until no errors are left.
4. **A builder-check** (standard and deep depth) runs: a fresh subagent sees only the
   log and the spec and reports where it would have to guess.
5. **You review an overview** and approve with an explicit yes.
6. **`grillspec approve spec`** records the approval and the spec's fingerprint;
   then the agent proposes what to remember (see [How memory works](memory.md)).

## Superpowers layout

One file, `docs/grillspec/specs/<id>.md`, which already holds the decision log:

```markdown
# <id>
## Intent
### Non-goals
## Decision log        (from the grill, unchanged)
## Requirements
### Requirement: <name>
<text with SHALL or MUST>
#### Scenario: RL-1 <name>
- **WHEN** …
- **THEN** …
## Open questions      (only when deferred decisions remain)
```

## OpenSpec layout

A standard OpenSpec change folder, `openspec/changes/<id>/`:

| File | Content |
|---|---|
| `proposal.md` | Why, What Changes, Capabilities, Impact |
| `specs/<capability>/spec.md` | deltas: ADDED / MODIFIED / REMOVED / RENAMED Requirements; a new capability starts with `## Purpose` |
| `design.md` | the decision log, plus Goals / Non-Goals and Open questions |
| `.openspec.yaml` | `skip_specs: true` only for a change with no behaviour change |

`openspec validate`, `show` and `archive` work on these changes as on any other.

## Scenario IDs

Every scenario name starts with an ID: a tag of 2–4 capital letters chosen for the
change, a dash and a number (`RL-3`). IDs are never renumbered or reused, because
plans and tests cite them and they outlive the change in your living specs. A
MODIFIED requirement keeps the IDs its scenarios already have. Requirement headers
carry no ID: OpenSpec matches requirements by their header text.

Living specs written before grillspec have scenarios without IDs, and OpenSpec
requires a MODIFIED block to keep its scenario names exactly. Such a kept scenario
gets the warning `scenario-id-legacy` instead of an error; new scenarios still need
an ID. To cite old scenarios in plans, give them IDs in `openspec/specs` first.

## What `grillspec validate` checks

Errors block `grillspec approve spec`; warnings do not.

| Rule | Level | What it means |
|---|---|---|
| `requirement-shall` | error | A requirement has no SHALL or MUST. |
| `requirement-scenario` | error | A requirement has no `#### Scenario:`. |
| `scenario-when-then` | error | A scenario lacks a WHEN or a THEN line. |
| `scenario-id` | error | A scenario name does not start with an ID like `RL-1`. |
| `scenario-id-duplicate` | error | An ID is used twice in the change. |
| `scenario-id-clash` | error | An ID is already used by a living spec or another active change. |
| `log-open-item` | error | A decision is still open and not deferred. |
| `deferred-not-listed` | error | A deferred decision is missing from Open questions. |
| `section-missing` | error | Superpowers: Intent or Requirements is missing. |
| `why-length` | error | OpenSpec: Why is not 50–1000 characters. |
| `what-changes-empty` | error | OpenSpec: What Changes is empty. |
| `deltas` | error | OpenSpec: no delta and no `skip_specs`, or both. |
| `delta-target` | error | OpenSpec: a MODIFIED or REMOVED requirement is not in the living spec. |
| `removed-reason` | error | OpenSpec: a REMOVED requirement lacks Reason or Migration. |
| `renamed-from-to` | error | OpenSpec: a rename lacks FROM or TO. |
| `scenario-format` | error | A level-4 heading inside a requirement is not `#### Scenario:`. |
| `requirement-length` | warning | A requirement is longer than 500 characters. |
| `scenario-id-legacy` | warning | OpenSpec: MODIFIED keeps a scenario without an ID from a spec written before grillspec. |
| `purpose` | warning | OpenSpec: a new capability's Purpose is missing or under 50 characters. |
| `delta-count` | warning | OpenSpec: more than 10 deltas; consider splitting the change. |
| `openspec` | warning | Findings of `openspec validate --strict`, when the OpenSpec CLI is installed. |

grillspec is stricter than OpenSpec in one place: a missing SHALL or MUST is an
error here, a warning in OpenSpec. If the OpenSpec CLI is installed but fails, you
get one `openspec: unavailable` warning and the result does not change.

## Builder-check

At standard and deep depth, a fresh subagent that sees only the log and the spec
answers one question: could it plan and build this without guessing? It reports at
most 10 findings — places it would guess, scenarios no test could check, decisions no
requirement carries out, requirements no decision supports — and edits nothing. The
agent fixes what facts settle and asks you the rest. In a harness without subagents,
the agent runs the same checklist itself and says that this check is weaker.

## Approval and edits after it

`grillspec approve spec` records the date and a fingerprint (`spec_hash`) of the spec
files: the spec file for Superpowers; `proposal.md`, `design.md` and the deltas for
OpenSpec. Line endings and trailing spaces do not count.

If the spec changes after approval:

- **before the plan is approved**, the change goes back to the `spec` phase until you
  approve it again;
- **after the plan is approved**, the phase stays and status shows the warning
  `spec changed after approval`, so work in progress is never locked.
