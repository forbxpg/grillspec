"""Edit user-owned text files without touching anything grillspec does not own."""

from __future__ import annotations

from ._edit import (
    BEGIN,
    END,
    BlockError,
    block_body,
    ensure_line,
    remove_block,
    remove_line,
    upsert_block,
)

__all__ = (
    "BEGIN",
    "END",
    "BlockError",
    "block_body",
    "ensure_line",
    "remove_block",
    "remove_line",
    "upsert_block",
)
