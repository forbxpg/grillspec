# Cursor tools

| Action | Cursor |
|---|---|
| Ask the user (multiple choice) | `AskQuestion` — dependable in Plan mode; in Agent mode it may be missing, so fall back to numbered options in plain text. |
| Dispatch a subagent | `Task` tool (agents in `.cursor/agents/`). |
| Track tasks | The todo tool of your Cursor version (unverified name). |
| Run a command | The terminal tool. |

Session start: the plugin's `sessionStart` hook injects this router and the
status line.
