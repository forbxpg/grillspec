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


def _span(
    lines: list[str], begin: str = BEGIN, end: str = END
) -> tuple[int, int] | None:
    """Locate a managed block.

    Args:
        lines: list[str] - File lines.
        begin: str - Begin marker line.
        end: str - End marker line.

    Returns:
        tuple[int, int] | None - Indexes of the begin and end marker lines, or
            None when there is no block.

    Raises:
        BlockError: If only one marker is present, either repeats, or end
            comes before begin.

    """
    # A UTF-8 BOM read as text sits in front of a marker on the first line.
    marks = [line.strip().removeprefix("\ufeff") for line in lines]
    begins = [i for i, line in enumerate(marks) if line == begin]
    ends = [i for i, line in enumerate(marks) if line == end]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        msg = "unbalanced grillspec markers; fix them by hand before running again"
        raise BlockError(msg)
    return begins[0], ends[0]


def block_body(text: str, *, begin: str = BEGIN, end: str = END) -> list[str] | None:
    """Return the lines between a managed block's markers.

    Args:
        text: str - File content.
        begin: str - Begin marker line.
        end: str - End marker line.

    Returns:
        list[str] | None - The body lines, or None when there is no block.

    """
    lines = _lines(text)
    span = _span(lines, begin, end)
    return None if span is None else lines[span[0] + 1 : span[1]]


def upsert_block(
    text: str,
    body: str,
    *,
    begin: str = BEGIN,
    end: str = END,
    after: tuple[str, str] | None = None,
) -> str:
    """Insert or replace a managed block.

    Args:
        text: str - File content.
        body: str - Block content, without markers.
        begin: str - Begin marker line.
        end: str - End marker line.
        after: tuple[str, str] | None - Markers of another block; a new block
            goes right after it when it exists, else at the end of the file.

    Returns:
        str - The new content; everything outside the block is unchanged.

    """
    newline = _newline(text)
    lines = _lines(text)
    block = [begin, *_lines(body), end]
    span = _span(lines, begin, end)
    if span is not None:
        first, last = span
        return _join([*lines[:first], *block, *lines[last + 1 :]], newline)
    anchor = _span(lines, *after) if after is not None else None
    if anchor is not None:
        head, rest = lines[: anchor[1] + 1], lines[anchor[1] + 1 :]
        tail = [""] if rest and rest[0].strip() else []
        return _join([*head, "", *block, *tail, *rest], newline)
    separator = [""] if lines else []
    return _join([*lines, *separator, *block], newline)


def remove_block(text: str, *, begin: str = BEGIN, end: str = END) -> str:
    """Remove a managed block and the blank line grillspec put before it.

    Args:
        text: str - File content.
        begin: str - Begin marker line.
        end: str - End marker line.

    Returns:
        str - The content without the block.

    """
    lines = _lines(text)
    span = _span(lines, begin, end)
    if span is None:
        return text
    first, last = span
    if first > 0 and not lines[first - 1].strip():
        first -= 1
    return _join([*lines[:first], *lines[last + 1 :]], _newline(text))


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
