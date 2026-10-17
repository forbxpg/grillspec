---
name: grillspec-archive
description: Use when a change is done (every plan task ticked, final review clean, branch finished) - to merge its spec deltas into the living specs or mark it archived, after showing the user exactly what will change.
---

# Archive the finished change

Archiving is the last step of a change: OpenSpec deltas become the living specs that
the next change starts from; a superpowers change is marked archived. It writes to
files many future changes read, so show the user exactly what will happen first.

`grillspec` below means the command on the `grillspec CLI:` line of your
session-start context (or `uvx grillspec`).

## 1. Check that it is done

Run `grillspec status`. The phase must be `done`: every plan task ticked, spec and
plan approved and unchanged. If not, say what is left (the status's next step) and
stop. The branch should be finished too (merged or in a pull request, see
`grillspec-finishing`); if it is not, ask whether to archive anyway.

## 2. Show the dry run

Run `grillspec archive --dry-run` and show its lines:

- OpenSpec: per capability, each rename, removal, modification and addition, any
  new living spec, and where the change folder moves; when the OpenSpec CLI is
  installed, it does the archive and grillspec's lines show what to expect.
- Superpowers: the change is marked archived.

## 3. Ask

"Archive this change?" Only an explicit yes counts. If the dry run refused (a
MODIFIED block that drops a living scenario, a rename whose source is missing, an
existing archive folder), show the reason and fix the delta first; never edit the
living specs by hand to make it pass.

## 4. Archive

Run `grillspec archive`. It writes every living spec only after all of them check
out, then moves the change folder, and clears the active change.

## 5. After

- Offer `grillspec-memory` for lessons from execution that future sessions should
  know.
- Name the changed files (living specs, the archive folder or the sidecar) and
  suggest committing them; never commit yourself.
- The working tree is idle: the next change starts with `grillspec-grill`.

## Red flags

| Thought | Reality |
|---|---|
| "Almost done, archive now." | Archive needs `done`. Finish the tasks or say what is left. |
| "The dry run refused, I'll fix the living spec." | Living specs change only through deltas. Fix the delta. |
| "They approved the plan, so they approve the archive." | The archive needs its own yes. |
