# How archiving works

When every plan task is ticked and the branch is finished, the agent archives the
change with the `grillspec-archive` skill: it shows `grillspec archive --dry-run`,
asks you, and then runs `grillspec archive`. Afterwards the working tree is idle and
the next change starts with a grill.

## When it is allowed

Only when the change's phase is `done`: the spec and the plan are approved and
unchanged since approval, and every task is ticked. Otherwise the command says what is
left and writes nothing.

## OpenSpec changes

The change's deltas merge into the living specs in `openspec/specs/`, in OpenSpec's
order, capability by capability:

| Order | Delta | Effect |
|---|---|---|
| 1 | RENAMED | the requirement's header changes; its text stays |
| 2 | REMOVED | the requirement is deleted (a missing one only warns) |
| 3 | MODIFIED | the requirement is replaced by the delta's full block |
| 4 | ADDED | the requirement is appended |

A capability with no living spec yet gets a new `spec.md` with its title, the delta's
Purpose and the added requirements. The change folder then moves to
`openspec/changes/archive/<date>-<id>/`.

The archive refuses — and writes nothing at all — when a renamed requirement is
missing or its new name is taken, a modified or added requirement does not fit, or a
MODIFIED block would drop a scenario the living requirement has (copy it into the
delta). Validator errors and an existing archive folder also stop it.

If the OpenSpec CLI is installed and runs, grillspec hands the archive to
`openspec archive <id> --yes`; otherwise its bundled archive applies the same rules.

## Superpowers changes

There are no living specs to merge into: the change's sidecar records
`archived = <date>`, and the change can no longer become active.

## After archiving

The agent offers to record lessons from execution in memory (see
[How memory works](memory.md)) and suggests committing the living specs and the
archive. It never commits for you.
