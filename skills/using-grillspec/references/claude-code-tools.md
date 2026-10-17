# Claude Code tools

| Action | Claude Code |
|---|---|
| Ask the user (multiple choice) | `AskUserQuestion`: 1–4 questions per call, 2–4 options each, `multiSelect` for non-exclusive choices; put the recommended option first and end its label with `(Recommended)`. The user can always answer "Other". |
| Dispatch a subagent | `Agent` tool; name the model explicitly for reviewers. |
| Track tasks | The todo / task tools your version provides. |
| Run a command | `Bash`. |
| Run a command in the background | `Bash` with `run_in_background: true`; you are told when it finishes. |

Session start: the plugin's `SessionStart` hook injects this router and the
status line.
