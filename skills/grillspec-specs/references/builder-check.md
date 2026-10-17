# Builder-check prompt

Give a fresh subagent this prompt, the decision log and the spec files. Nothing else:
not the conversation, not your notes.

---

You are about to plan and build this change, and you only have the decision log and
the spec below. Do not edit anything. Read them and answer one question: could you
write the plan and the code without guessing anywhere?

Report at most 10 findings, most important first, one line each:

`<type> <where>: <what> → <suggested fix>`

Types:

- `guess`: you would have to assume something the spec does not say.
- `untestable`: a scenario has no observable outcome a test could check.
- `decision-not-reflected`: a Settled decision that no requirement carries out.
- `requirement-without-decision`: a requirement that no decision in the log supports.

`<where>` is a requirement name or a scenario ID. If you find nothing, answer
`no findings`.
