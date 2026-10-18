# grillspec documentation

grillspec turns a request into a grilled decision log, a spec, a plan and tested code.
Each mechanism below exists for one reason and has a context cost; the cost of every
skill is in [What grillspec costs in tokens](tokens.md).

| Mechanism | Page | Why it exists | Context cost |
|---|---|---|---|
| Bootstrap | [How the bootstrap works](how-it-works/bootstrap.md) | A skill the agent does not know about never triggers. | always on: router and catalogue |
| Grilling | [How grilling works](how-it-works/grilling.md) | A design built on a guess costs more than ten extra questions. | on demand |
| Council | [How the council works](how-it-works/council.md) | Independent perspectives catch what one line of reasoning misses. | on demand; external CLIs use their own tokens |
| Specs | [How specs work](how-it-works/specs.md) | Requirements with scenario IDs make tests traceable to decisions. | on demand |
| Memory | [How memory works](how-it-works/memory.md) | A fact learned once should not be re-derived every session. | always on: the memory block |
| Plans | [How plans work](how-it-works/plans.md) | The plan holds the decisions an implementer cannot make alone. | on demand |
| Execution | [How execution works](how-it-works/execution.md) | Test-first tasks and a fresh review keep the code honest to the spec. | on demand |
| Session memory | [How session memory works](how-it-works/session-memory.md) | A new session should not need the last one explained again. | always on: the resume brief (≤ 1,500 tokens) |
| Archive | [How archiving works](how-it-works/archive.md) | Living specs stay the record of what the system does. | on demand |
| Phase gates | [How phase gates work](how-it-works/gates.md) | Code written before the spec is approved is a guess. | none: a hook, not context |
| Token costs | [What grillspec costs in tokens](tokens.md) | "Costs little" has to be a number. | — |

Also: [Installation](installation.md) · [Configuration](configuration.md)
