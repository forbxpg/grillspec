"""Hook entry points: what grillspec tells a harness at session start."""

from __future__ import annotations

from ._session_start import Harness, render_session_start, session_context

__all__ = ("Harness", "render_session_start", "session_context")
