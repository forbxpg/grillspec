---
name: using-grillspec
description: Use when starting any conversation, and before acting on any request that involves choosing between options - routes work through grilling, specs, plans and execution so the agent never guesses what the user would decide.
---

# Using grillspec

grillspec spends questions up front so you never have to guess later. A choice
between options is a decision, and decisions belong to the user.

## The rule

Before you act on a request — before clarifying questions, before exploring code —
decide which row applies:

| The request | Do |
|---|---|
| has no choice between options: a typo, a rename, formatting, a fix whose cause and remedy are both certain | Just do it. |
| has a decision but is small: one function or file, reversible, no new interface | Quick grill in chat: name the decision, give your recommendation, ask. No files. |
| adds or changes a feature, module, interface, schema, infrastructure, or anything hard to reverse | Run the full pipeline below. |

Unsure between two rows? Take the lower one. One extra question costs less than
one rework.

Debugging, test-driven development and verification skills keep their own triggers
whatever the row.

## The pipeline

`grill → spec (+ memory) → plan → execute → archive`

| Phase | Skill | Leaves behind |
|---|---|---|
| grill | `grilling` | a decision log |
| spec | `writing-specs`, then `extracting-memory` | an approved spec; approved memory entries |
| plan | `writing-plans` | an approved plan |
| execute | `subagent-driven-development` or `executing-plans`, with `test-driven-development`, `systematic-debugging`, `verification-before-completion` | code and green tests |
| archive | `archiving-changes` | the change merged into the living specs, or marked implemented |

If a skill named here is not installed yet, tell the user which phase you are in
and follow the phase by hand.

No `.grillspec/config.toml` in the project? Use the `init` skill first.

## Where you are

Each session starts with a line like
`grillspec: phase=spec change=2026-10-17-login next=write and approve the spec`.
When unsure, run `grillspec status` (or `python3 <plugin root>/scripts/grillspec.py
status`). Phases: `idle`, `spec`, `plan`, `execute`, `done`.

Approval of a spec or a plan comes only from an explicit reply from the user —
never inferred from silence, from a "looks fine so far", or from your own review.
If the user insists on skipping a phase, do it, and say once what stays unverified.

## Facts and decisions

Look facts up yourself: files, git history, configuration, documentation, a CLI's
`--help`. Asking the user what you could have checked wastes their time. Put every
decision to the user: what depends on their product, taste or risk is theirs.

## Asking

Each decision you put to the user carries your recommendation, first and marked
`(Recommended)`, with the real trade-off of each alternative. Use the harness's
multiple-choice tool when it has one; otherwise write numbered options in plain
text and accept a number or free text as the answer.

## Language

Reply in the language of the user's latest message. Write specs and plans in the
project's artifact language (`spec.artifacts_language`; `auto` means the language
of the project's existing docs, or of the conversation in an empty repository).
Keep OpenSpec keywords in English: `SHALL`, `MUST`, `WHEN`, `THEN`, `AND`, and the
section headers.

## Other workflow plugins

If Superpowers or another workflow router is also active, tell the user once to
keep only one of them enabled. Until they do, follow grillspec for planning and
for its phase gates.

## Red flags

| Thought | Reality |
|---|---|
| "This is obvious, I'll just build it." | Obvious is where unchecked assumptions live. Check the rule table. |
| "I'll pick a sensible default." | Picking between options is a decision. Ask. |
| "Let me explore the code first, then ask." | Decide the row first; looking things up is part of the grill. |
| "The user is in a hurry." | Name the decision in one sentence and ask. |
| "They approved the idea, so the spec is approved." | Approval is an explicit reply to the written artifact. |

## Harness tools

Skills name actions — ask the user, dispatch a subagent, track tasks, run a
command. How each harness spells them:

- Claude Code: `references/claude-code-tools.md`
- Cursor: `references/cursor-tools.md`
- Codex: `references/codex-tools.md`
- Antigravity: `references/antigravity-tools.md`
- GigaCode: `references/gigacode-tools.md`
