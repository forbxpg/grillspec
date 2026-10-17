"""Build the session-start context and shape it for each harness."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import TYPE_CHECKING

from grillspec.config import load_config
from grillspec.paths import data_root
from grillspec.state import compute_status

if TYPE_CHECKING:
    from pathlib import Path

ROUTER = "using-grillspec"


class Harness(StrEnum):
    """Coding agents grillspec supports."""

    CLAUDE = "claude"
    CURSOR = "cursor"
    CODEX = "codex"
    ANTIGRAVITY = "antigravity"
    GIGACODE = "gigacode"


def _router_body() -> str:
    """Read the router skill without its frontmatter.

    Returns:
        str - The router's Markdown body.

    """
    text = (data_root() / "skills" / ROUTER / "SKILL.md").read_text(encoding="utf-8")
    _, _, rest = text.partition("\n---\n")
    return rest.strip()


def session_context(root: Path) -> str:
    """Build what a session should know about grillspec when it starts.

    Never raises: any failure becomes a warning line, so a broken install cannot
    block the agent.

    Args:
        root: Path - Project root.

    Returns:
        str - Router body, the status line and one line per warning.

    """
    parts: list[str] = []
    warnings: list[str] = []
    try:
        parts.append(_router_body())
    except OSError as error:
        warnings.append(f"grillspec router unreadable: {error}")
    try:
        loaded = load_config(root)
        status = compute_status(root, loaded.config)
        parts.append(status.line())
        warnings.extend((*loaded.warnings, *status.warnings))
    except Exception as error:  # ruff: ignore[blind-except] - a hook must never fail the session
        warnings.append(f"grillspec bootstrap failed: {type(error).__name__}: {error}")
    parts.extend(f"WARNING: {warning}" for warning in warnings)
    return "\n\n".join(parts)


def render_session_start(harness: Harness, context: str) -> str:
    """Shape the session-start context the way a harness reads it.

    Args:
        harness: Harness - Target harness.
        context: str - Text to inject.

    Returns:
        str - One JSON object.

    Raises:
        ValueError: For GigaCode, which bootstraps through ``GIGACODE.md``.

    """
    if harness in {Harness.CLAUDE, Harness.CODEX}:
        payload: object = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            }
        }
    elif harness is Harness.CURSOR:
        payload = {"additional_context": context}
    elif harness is Harness.ANTIGRAVITY:
        payload = {"injectSteps": [{"systemMessage": {"systemMessage": context}}]}
    else:
        msg = f"{harness} has no session-start hook; it imports the router instead"
        raise ValueError(msg)
    return json.dumps(payload)
