---
name: grillspec-grill
description: Use when a change involves decisions the user should make - before writing a spec, plan or code for a feature, module, interface, schema or infrastructure change - and when the user says grill, interview me, let's plan, or asks how to build something. Interviews until nothing is left to guess and keeps a decision log that survives context loss.
---

# Grill the user before building

A design built on a guess costs more than ten extra questions. Interview the user
until you could write the spec without guessing anywhere, and write every answer
to the decision log as you go: the log, not your memory, is what the spec is
written from.

`grillspec` below means the command on the `grillspec CLI:` line of your
session-start context (or `uvx grillspec`).

## 1. Start

1. Read the session-start status line (or run `grillspec status --json`).
   - Phase `grill`: you are resuming. Read the log at its `log=` path, then go
     straight to step 3 with its Open items. Do not re-ask Settled ones, and do not
     re-explore the code you already explored for them.
   - Another change is active in `grill`, `spec`, `plan` or `execute` and the
     request is not part of it: name it and its phase and ask — continue it / start
     the new one here (the old one stays; `grillspec use <id>` returns to it) /
     start the new one in a separate worktree (`git worktree add ../<repo>-<slug>`,
     then continue there).
2. Ask the **setup question**, one message:
   - a slug for the change (lowercase kebab-case, proposed from the request);
   - the depth — recommend by stakes: `quick` for a small, reversible change;
     `standard` for a feature; `deep` for anything hard to reverse (schema, public
     API, infrastructure, security);
   - a council, only if a `grillspec-council` skill is installed and
     `council.enabled` is `ask` in the config.
3. Run `grillspec new <slug> --depth <depth>` (add `--council` when chosen, and
   `--switch` when the user chose to start it while another change is active).
   If the depth or council differs from the configured default, offer once to
   make it the default in the user's config.

## 2. Build the decision tree

Map every decision the change needs, with the decisions that hang off it. The
**frontier** is every decision whose prerequisites are settled. Write the whole
frontier under `### Open` before asking anything:

```markdown
- [ ] Q3 Retry policy for failed webhooks (after D2)
```

**Facts are yours, decisions are theirs.** Look facts up: files, git history,
config, docs, a `--help`. A quick lookup you do inline; a broad exploration you
hand to a subagent when the harness has one, and keep asking the questions that
do not depend on it. Never ask the user what you could have checked. A choice
between options is a decision even when one option looks obvious — ask it.

## 3. Ask

| Depth | How | Budget |
|---|---|---|
| quick | Rounds in plain text: the whole frontier, numbered, each with `➡️` your recommendation, worded so "yes" accepts all of them | ~5 decisions |
| standard | One decision at a time; up to 4 small independent ones together | ~15 decisions |
| deep | One decision at a time | none |

For standard and deep use the harness's multiple-choice tool when it has one
(see `using-grillspec/references/`), otherwise numbered options in text.

Every decision you put carries: your recommendation first, marked
`(Recommended)`; the real trade-off of each option; whether it is cheap or costly
to reverse. With a council: add its options and any dissent — on standard for root
and hard-to-reverse decisions, on deep for every decision. Same-model agreement is
a weak signal; say so.

## 4. Log every answer — immediately

In the same turn as your next question, move the item from Open to Settled:

```markdown
- [x] D1 Auth — **JWT + refresh tokens** · user · alternatives: server sessions (simpler revoke) · reversible: costly
  > "the mobile client has no cookies"
```

- Source, exactly one of: `user` (they chose), `accepted` (they said yes to your
  recommendation), `delegated` ("you decide": take your recommendation, do not ask
  again), `agent's call` (only for choices with no effect on the product, such as
  an internal name), `accepted without discussion` (see Budget).
- "Skip" / "later": leave it Open and append `· deferred`.
- Quote the user's own words when they answered in their own words.
- Changed mind: never edit a Settled line. Add a new entry and mark the old one
  `- [~] D1 … superseded by D6`.
- Write in the project's artifact language; OpenSpec keywords stay English.
- Never write secrets, tokens or passwords into the log: write `<redacted>`.
- Bump `asked=` in the `<!-- grillspec: … -->` line when you put a decision to the
  user — not when you add it to Open.
- New branches that an answer opens go under Open right away.

## 5. Budget

The budget counts decisions put to the user, batched or not; follow-up questions
about the same decision and fact lookups do not count. When `asked` reaches it,
list every remaining Open item with your recommendation and ask: continue, or
accept these? Accepted ones are logged as `accepted without discussion`.

## 6. Split

If the tree turns out to hold independent changes, name them and offer to split.
On yes, create each with `grillspec new <slug> --switch`, move its Open items to
its log, return with `grillspec use <id>`, and finish one change at a time.

## 7. Finish

When Open holds nothing but explicitly deferred items:

1. Play back the shared understanding in 3–10 lines. List separately every
   `agent's call`, `delegated` and `deferred` item.
2. Ask: "Do we share the same understanding?" Only an explicit yes counts.
3. On yes, run `grillspec approve grill`.
4. Name the log file and suggest committing it — never commit it yourself.
5. Continue with the `grillspec-specs` skill. If it is not installed, say so and
   stop: the log is complete and the phase is now `spec`.

## Red flags

| Thought | Reality |
|---|---|
| "This one is obvious." | Obvious is where unchecked assumptions live. Ask it. |
| "They're in a hurry, I'll decide." | Name the decision in one sentence and ask. One question beats one rework. |
| "I'll ask that later." | Later is after the guess is built in. Put it under Open now. |
| "I'll write the log at the end." | The end comes after compaction. Write it now. |
| "That's a fact, not a decision." | If two reasonable people could choose differently, it is a decision. |
| "They said yes earlier, so this is approved too." | Each decision and the final confirmation need their own yes. |
