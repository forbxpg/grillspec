"""The project memory block in AGENTS.md: small, one fact per line, never erased."""

from __future__ import annotations

import re
from dataclasses import dataclass

from grillspec.blocks import BEGIN, END, BlockError, block_body, upsert_block

_ROUTER_BROKEN = "unbalanced grillspec markers in AGENTS.md; fix them by hand"

MEMORY_BEGIN = "<!-- grillspec:memory:begin -->"
MEMORY_END = "<!-- grillspec:memory:end -->"
HEADER = "## Project memory (grillspec)"
CATEGORIES = ("command", "convention", "constraint", "gotcha", "docs")
MAX_ENTRIES = 40
MAX_TEXT = 160
_ENTRY = re.compile(
    r"^- \[(" + "|".join(CATEGORIES) + r")\] (.+) \(([A-Za-z0-9._-]+)\)$"
)
_CHANGE = re.compile(r"[A-Za-z0-9._-]+")


class MemoryBlockError(Exception):
    """The memory block cannot be read or changed as asked."""


@dataclass(frozen=True)
class Entry:
    """One remembered fact.

    Attributes:
        category: str - One of ``CATEGORIES``.
        text: str - The fact, one line.
        change: str - Id of the change it came from.

    """

    category: str
    text: str
    change: str

    def line(self) -> str:
        """Render the entry as its block line.

        Returns:
            str - ``- [<category>] <text> (<change>)``.

        """
        return f"- [{self.category}] {self.text} ({self.change})"


def _body(text: str) -> list[str] | None:
    """Return the memory block's lines between its markers.

    Args:
        text: str - AGENTS.md content.

    Returns:
        list[str] | None - Body lines, or None when there is no block.

    Raises:
        MemoryBlockError: If the memory markers are unbalanced.

    """
    try:
        return block_body(text, begin=MEMORY_BEGIN, end=MEMORY_END)
    except BlockError:
        msg = "unbalanced grillspec memory markers in AGENTS.md; fix them by hand"
        raise MemoryBlockError(msg) from None


def read_entries(text: str) -> list[Entry]:
    """Read the remembered facts.

    Args:
        text: str - AGENTS.md content.

    Returns:
        list[Entry] - Entries in file order; empty without a block.

    Raises:
        MemoryBlockError: If the markers are unbalanced or a line in the block
            is neither blank, the header, nor an entry.

    """
    entries: list[Entry] = []
    for number, line in enumerate(_body(text) or [], 1):
        stripped = line.strip()
        if not stripped or stripped == HEADER:
            continue
        match = _ENTRY.match(stripped)
        if match is None:
            msg = f"line {number} of the memory block is not an entry: {stripped!r}"
            raise MemoryBlockError(msg)
        entries.append(Entry(*match.groups()))
    return entries


def _key(text: str) -> str:
    """Normalise a fact for duplicate detection.

    Args:
        text: str - Fact text.

    Returns:
        str - Whitespace collapsed, case folded.

    """
    return " ".join(text.split()).casefold()


def _check(entry: Entry) -> None:
    """Refuse an entry that would break the block or the format.

    Args:
        entry: Entry - The candidate.

    Raises:
        MemoryBlockError: If the category, text or change id is not allowed.

    """
    if entry.category not in CATEGORIES:
        msg = (
            f"unknown category {entry.category!r}; use one of: {', '.join(CATEGORIES)}"
        )
        raise MemoryBlockError(msg)
    text = entry.text.strip()
    # splitlines() also breaks on \u2028, \x85, \x0b, \x0c, \x1c-\x1e, so any of
    # them would split the entry when the file is read back.
    one_line = bool(text) and len(entry.text.splitlines()) == 1
    safe = "<!--" not in text and not text.startswith("#")
    if not (one_line and safe and len(text) <= MAX_TEXT):
        rule = "not starting with '#' and without '<!--'"
        msg = f"memory text must be one line of 1-{MAX_TEXT} characters, {rule}"
        raise MemoryBlockError(msg)
    if not _CHANGE.fullmatch(entry.change):
        msg = "change id may use only letters, digits, '.', '_' and '-'"
        raise MemoryBlockError(msg)


def _write(text: str, entries: list[Entry]) -> str:
    """Rewrite the memory block with these entries.

    Args:
        text: str - AGENTS.md content.
        entries: list[Entry] - Entries to keep, in order.

    Returns:
        str - New content; everything outside the block is unchanged.

    Raises:
        MemoryBlockError: If the router block's markers are unbalanced.

    """
    body = "\n".join([HEADER, *(entry.line() for entry in entries)])
    try:
        return upsert_block(
            text, body, begin=MEMORY_BEGIN, end=MEMORY_END, after=(BEGIN, END)
        )
    except BlockError:
        raise MemoryBlockError(_ROUTER_BROKEN) from None


def add_entry(text: str, entry: Entry) -> str:
    """Remember one more fact.

    Args:
        text: str - AGENTS.md content (may be empty).
        entry: Entry - The fact.

    Returns:
        str - New content, with the block created after the router block (or at
            the end) when it did not exist.

    Raises:
        MemoryBlockError: If the entry is malformed, already stored, or the block
            already holds ``MAX_ENTRIES`` entries.

    """
    _check(entry)
    entry = Entry(entry.category, entry.text.strip(), entry.change)
    entries = read_entries(text)
    for number, existing in enumerate(entries, 1):
        if _key(existing.text) == _key(entry.text):
            msg = f"already remembered as entry {number}: {existing.line()}"
            raise MemoryBlockError(msg)
    if len(entries) >= MAX_ENTRIES:
        full = f"memory is full ({MAX_ENTRIES}/{MAX_ENTRIES} entries)"
        msg = f"{full}: retire entries or move them to docs/grillspec/memory/"
        raise MemoryBlockError(msg)
    return _write(text, [*entries, entry])


def retire_entry(text: str, number: int) -> str:
    """Forget one fact.

    Args:
        text: str - AGENTS.md content.
        number: int - 1-based entry number, as ``memory list`` shows it.

    Returns:
        str - New content.

    Raises:
        MemoryBlockError: If there is no such entry.

    """
    entries = read_entries(text)
    if not 1 <= number <= len(entries):
        msg = f"no entry {number}; the memory block has {len(entries)} entries"
        raise MemoryBlockError(msg)
    return _write(text, [e for n, e in enumerate(entries, 1) if n != number])
