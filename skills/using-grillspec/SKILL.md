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
| has a decision but is small: one function or file, reversible, no new interface | Ask in chat: name the decision, give your recommendation, ask. One question, no skill, no files. |
| adds or changes a feature, module, interface, schema, infrastructure, or anything hard to reverse | Run the full pipeline below. |

Unsure between two rows? Take the lower one. One extra question costs less than
one rework.

Debugging, test-driven development and verification skills (`grillspec-debugging`,
`grillspec-tdd`, `grillspec-verification`) keep their own triggers
whatever the row.

## The pipeline

`grill → spec (+ memory) → plan → execute → archive`

| Phase | Skill | Leaves behind |
|---|---|---|
| grill | `grillspec-grill`, with `grillspec-council` when the council is on | a decision log (Open / Settled), confirmed by the user |
| spec | `grillspec-specs`, then `grillspec-memory` | an approved spec; approved memory entries |
| plan | `grillspec-plans` | an approved plan |
| execute | `grillspec-subagent-execution` or `grillspec-inline-execution` (the plan's executor), with `grillspec-tdd`, `grillspec-debugging`, `grillspec-verification`, then `grillspec-finishing` | code and green tests; every task ticked |
| archive | `grillspec-archive` | the change merged into the living specs, or marked implemented |

If a skill named here is not installed yet, tell the user which phase you are in
and follow the phase by hand.

No `.grillspec/config.toml` in the project and the request is in row 2 or 3? Then
offer the `grillspec-init` skill once; if the user declines, ask in chat without files.
Row-1 work never needs it.

## Where you are

Each session starts with a line like
`grillspec: phase=grill change=2026-10-17-login next=continue grilling: 3 open questions`.
When unsure, run `grillspec status`, using the command on the `grillspec CLI:` line
of the session-start context (or `uvx grillspec` where no plugin is installed). Phases: `idle`, `grill`, `spec`, `plan`,
`execute`, `done`.

Confirming a grill and approving a spec or a plan come only from an explicit reply
from the user —
never inferred from silence, from a "looks fine so far", or from your own review.
An explicit "no questions" or "just do it" is consent to proceed on your own
judgment. Before you change any file, write the decisions you are taking for the
user as a visible list headed "Assumptions" — in your reply, not only in your
reasoning; one line each, with what to change if it is wrong. Then do the work,
and repeat the list in your final message. "I'm in a hurry" alone is not that consent: still ask the one decision
that matters most, with your recommendation.

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
| "The user is in a hurry." | Ask the one decision that matters — unless they said no questions: then list your assumptions first and proceed. |
| "They approved the idea, so the spec is approved." | Approval is an explicit reply to the written artifact. |

## Harness tools

Skills name actions — ask the user, dispatch a subagent, track tasks, run a
command. How each harness spells them:

- Claude Code: `references/claude-code-tools.md`
- Cursor: `references/cursor-tools.md`
- Codex: `references/codex-tools.md`
- Antigravity: `references/antigravity-tools.md`
- GigaCode: `references/gigacode-tools.md`
