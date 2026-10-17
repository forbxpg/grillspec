# Antigravity tools

| Action | Antigravity |
|---|---|
| Ask the user (multiple choice) | No dedicated tool: write numbered options in plain text. |
| Dispatch a subagent | `invoke_subagent` (`self` for full work, `research` for read-only). |
| Track tasks | A task artifact: `write_to_file` with `IsArtifact: true` and `ArtifactType: "task"`, updated as steps finish. `manage_task` manages background processes, not todos. |
| Run a command | The terminal tool. |
| Run a command in the background | The terminal tool; `manage_task` follows background processes. |

Session start: the plugin's `hooks.json` injects this router (verified per surface
by the smoke test; until then, rely on this skill's description).
