"""Skip fenced code blocks the way CommonMark delimits them."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")


def lines_outside_fences(text: str) -> Iterator[str]:
    """Yield the lines of a Markdown text that are not inside a fenced code block.

    A fence opens with three or more backticks or tildes (indented at most three
    spaces) and closes with a line of the same character, at least as long, indented
    at most three spaces, and nothing else. An unclosed fence runs to the end of the
    text, as in CommonMark.

    Args:
        text: str - Markdown text.

    Yields:
        str - Lines outside fences, fence lines excluded.

    """
    fence: str | None = None
    for line in text.splitlines():
        if fence is None:
            opened = _OPEN.match(line)
            if opened:
                fence = opened.group(1)
                continue
            yield line
            continue
        closing = _CLOSE.match(line)
        if (
            closing
            and closing.group(1)[0] == fence[0]
            and len(closing.group(1)) >= len(fence)
        ):
            fence = None
