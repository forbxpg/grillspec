"""Managed blocks and single lines, keeping the file's newline style."""

from __future__ import annotations

BEGIN = "<!-- grillspec:begin -->"
END = "<!-- grillspec:end -->"


class BlockError(Exception):
    """The managed-block markers are unbalanced, so the block cannot be edited."""


def _newline(text: str) -> str:
    r"""Return the newline sequence a text uses.

    Args:
        text: str - File content.

    Returns:
        str - ``\r\n`` when the text uses it, else ``\n``.

    """
    return "\r\n" if "\r\n" in text else "\n"


def _lines(text: str) -> list[str]:
    """Split text into lines without their newline characters.

    Args:
        text: str - File content.

    Returns:
        list[str] - The lines.

    """
    return text.splitlines()


def _join(lines: list[str], newline: str) -> str:
    """Join lines with a trailing newline, or return empty text.

    Args:
        lines: list[str] - Lines without newlines.
        newline: str - Newline sequence.

    Returns:
        str - The text.

    """
    return newline.join(lines) + newline if lines else ""


def _span(lines: list[str]) -> tuple[int, int] | None:
    """Locate the managed block.

    Args:
        lines: list[str] - File lines.

    Returns:
        tuple[int, int] | None - Indexes of the begin and end marker lines, or
            None when there is no block.

    Raises:
        BlockError: If only one marker is present, either repeats, or end
            comes before begin.

    """
    begins = [i for i, line in enumerate(lines) if line.strip() == BEGIN]
    ends = [i for i, line in enumerate(lines) if line.strip() == END]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        msg = "unbalanced grillspec markers; fix them by hand before running again"
        raise BlockError(msg)
    return begins[0], ends[0]


def upsert_block(text: str, body: str) -> str:
    """Insert or replace the managed block.

    Args:
        text: str - File content.
        body: str - Block content, without markers.

    Returns:
        str - The new content; everything outside the block is unchanged.

    """
    newline = _newline(text)
    lines = _lines(text)
    block = [BEGIN, *_lines(body), END]
    span = _span(lines)
    if span is None:
        separator = [""] if lines else []
        return _join([*lines, *separator, *block], newline)
    begin, end = span
    return _join([*lines[:begin], *block, *lines[end + 1 :]], newline)


def remove_block(text: str) -> str:
    """Remove the managed block and the blank line grillspec put before it.

    Args:
        text: str - File content.

    Returns:
        str - The content without the block.

    """
    lines = _lines(text)
    span = _span(lines)
    if span is None:
        return text
    begin, end = span
    if begin > 0 and not lines[begin - 1].strip():
        begin -= 1
    return _join([*lines[:begin], *lines[end + 1 :]], _newline(text))


def ensure_line(text: str, line: str) -> str:
    """Append a line unless the text already has it.

    Args:
        text: str - File content.
        line: str - Exact line to have.

    Returns:
        str - The content with the line.

    """
    lines = _lines(text)
    if line in lines:
        return text
    return _join([*lines, line], _newline(text))


def remove_line(text: str, line: str) -> str:
    """Remove every exact occurrence of a line.

    Args:
        text: str - File content.
        line: str - Exact line to drop.

    Returns:
        str - The content without the line.

    """
    lines = _lines(text)
    if line not in lines:
        return text
    return _join([kept for kept in lines if kept != line], _newline(text))
