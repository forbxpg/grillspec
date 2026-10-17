# GigaCode tools

| Action | GigaCode CLI |
|---|---|
| Ask the user (multiple choice) | No confirmed tool: write numbered options in plain text. |
| Dispatch a subagent | Subagents from `.gigacode/agents/` (unverified tool name). |
| Track tasks | The todo tool if present (unverified); otherwise a checklist in the plan file. |
| Run a command | The shell tool. |

Run the CLI as `uvx grillspec <command>` (or `grillspec` if installed with pip).

Session start: `GIGACODE.md` imports this skill (`grillspec install --harness
gigacode`). Before a plan is approved, suggest `/plan` mode so files stay
read-only.
