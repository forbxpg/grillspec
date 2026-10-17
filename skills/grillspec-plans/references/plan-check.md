# Plan-check prompt

Give a fresh subagent this prompt, the approved spec and the plan. Nothing else.

---

You are about to execute this plan, task by task, and you only have the spec and the
plan below. Do not edit anything. Could you carry out every task without guessing?

Report at most 10 findings, most important first, one line each:

`<type> <task>: <what> → <suggested fix>`

Types:

- `guess`: a step leaves a choice you would have to make yourself.
- `interface-mismatch`: a task consumes a name or signature no earlier task produces.
- `untested-scenario`: a scenario the plan claims to cover but no step tests.
- `transcript`: a step writes code its signature and tests already determine.

If you find nothing, answer `no findings`.
