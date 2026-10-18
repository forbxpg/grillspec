"""Phase gates: refuse code edits while a change is grilled, specced or planned."""

from __future__ import annotations

from ._adapters import pre_tool
from ._gate import GATED, ToolCall, decide
from ._patch import patch_paths
from ._shell import shell_targets

__all__ = ("GATED", "ToolCall", "decide", "patch_paths", "pre_tool", "shell_targets")
