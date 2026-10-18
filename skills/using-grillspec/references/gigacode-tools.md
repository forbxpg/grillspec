# GigaCode tools

| Action | GigaCode CLI |
|---|---|
| Ask the user (multiple choice) | `ask_user_question`; if it fails, numbered options in plain text. |
| Dispatch a subagent | `agent`. |
| Track tasks | `todo_write`; otherwise a checklist in the plan file. |
| Run a command | `run_shell_command`. |
| Run a command in the background | `run_shell_command` with `is_background: true`. |
| Load a skill | `skill` with `{"skill": "<name>"}`. |

Run the CLI as the `grillspec CLI:` line of `gigacode-context.md` says (the extension
loads it every session), else `grillspec` if installed with pip.

Session start: GigaCode discards session-start hook output, so the router and that line
arrive as extension context files instead. Phase gates run only when the user enabled
GigaCode hooks (`hooksConfig.enabled`); otherwise never edit code while the active
change is in `grill`, `spec` or `plan`.
