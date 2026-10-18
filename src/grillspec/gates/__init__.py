"""Phase gates: refuse code edits while a change is grilled, specced or planned."""

from __future__ import annotations

from ._gate import ToolCall, decide
from ._patch import patch_paths
from ._shell import shell_targets

__all__ = ("ToolCall", "decide", "patch_paths", "shell_targets")
