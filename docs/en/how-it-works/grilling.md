# How grilling works

Before a change that involves decisions, the agent interviews you with the
`grillspec-grill` skill until it could write the spec without guessing anywhere.
Facts it looks up itself; decisions it puts to you, each with a recommendation.

## Starting

The agent asks one setup question — a name for the change, the depth, and (when a
council is installed) whether to use one — then runs `grillspec new <slug>`. That
creates the change, makes it active and starts its decision log. The change is now
in the `grill` phase.
With a council, hard decisions also carry the views of other models; see
[How the council works](council.md).

## Depths

| Depth | How questions come | Budget |
|---|---|---|
| `quick` | In rounds: every question that can be asked now, numbered, each with a recommendation; "yes" accepts them all | about 5 decisions |
| `standard` | One decision at a time; up to four small independent ones together | about 15 decisions |
| `deep` | One decision at a time | none |

The budget counts decisions put to you, not messages. When it runs out, the agent
lists what is still open with its recommendations, and you choose: keep going, or
accept them.

## The decision log

The log lives in the change's own artifact: the `## Decision log` section of
`docs/grillspec/specs/<id>.md` (superpowers backend) or of
`openspec/changes/<id>/design.md` (OpenSpec backend). The agent updates it after
every answer. (With OpenSpec, `openspec validate` reports the change as invalid
until the spec phase adds its first delta; that is expected while grilling.)

```markdown
## Decision log

<!-- grillspec: depth=standard council=no budget=15 asked=4 -->

### Open
- [ ] Q5 Retry policy for failed webhooks (after D2)

### Settled
- [x] D1 Auth — **JWT + refresh tokens** · user · alternatives: server sessions · reversible: costly
  > "the mobile client has no cookies"
- [x] D2 Webhook delivery — **at-least-once** · accepted
- [x] D3 Log format — **JSON lines** · agent's call
- [~] D1 superseded by D6
```

## Who decided what

| Mark | Meaning |
|---|---|
| `user` | You chose. |
| `accepted` | You said yes to the agent's recommendation. |
| `delegated` | You said "you decide"; the agent took its recommendation. |
| `agent's call` | The agent decided something with no effect on the product, such as an internal name. |
| `accepted without discussion` | Left open when the budget ran out, and you accepted the recommendation. |
| `deferred` | You said "later"; it stays open and becomes an open question in the spec. |

## Resuming

Context compaction or a new session loses nothing: at session start the agent sees
`phase=grill … next=continue grilling: 3 open questions`, reads the log, and asks
the next open question. Settled decisions are never asked again.

## Finishing

When nothing is left open, the agent plays the result back in a few lines, listing
everything it decided on its own, and asks whether you share the same
understanding. Only an explicit yes counts: it runs `grillspec approve grill`, the
change moves to the `spec` phase, and the spec is written from the log (see
[How specs work](specs.md)). The agent never commits the log for you.
