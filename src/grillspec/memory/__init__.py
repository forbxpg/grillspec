"""Project memory: the facts every session should know, kept small."""

from __future__ import annotations

from ._block import (
    CATEGORIES,
    HEADER,
    MAX_ENTRIES,
    MAX_TEXT,
    MEMORY_BEGIN,
    MEMORY_END,
    Entry,
    MemoryBlockError,
    add_entry,
    read_entries,
    retire_entry,
)

__all__ = (
    "CATEGORIES",
    "HEADER",
    "MAX_ENTRIES",
    "MAX_TEXT",
    "MEMORY_BEGIN",
    "MEMORY_END",
    "Entry",
    "MemoryBlockError",
    "add_entry",
    "read_entries",
    "retire_entry",
)
