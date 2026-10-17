# Codex tools

| Action | Codex |
|---|---|
| Ask the user (multiple choice) | `request_user_input` — Plan mode only; elsewhere write numbered options in plain text. |
| Dispatch a subagent | `spawn_agent` with `fork_turns: "none"` for a clean context; `wait_agent` to collect; `followup_task` to resume a child. Needs `[features] multi_agent = true` in `~/.codex/config.toml`. |
| Track tasks | `update_plan`. |
| Run a command | The shell tool. |

Session start: the plugin's `SessionStart` hook injects this router once the user
has trusted the plugin's hooks (`/hooks`). Without that, rely on this skill's
description.
