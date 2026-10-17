"""Tests for managed-block and line edits (Review Focus 3, 4)."""

from __future__ import annotations

import pytest

from grillspec.blocks import (
    BEGIN,
    END,
    BlockError,
    ensure_line,
    remove_block,
    remove_line,
    upsert_block,
)


def test_append_block_to_existing_text():
    out = upsert_block("# Agents\n\nmine\n", "hello\n")
    assert out == f"# Agents\n\nmine\n\n{BEGIN}\nhello\n{END}\n"


def test_block_into_empty_text():
    assert upsert_block("", "hello\n") == f"{BEGIN}\nhello\n{END}\n"


def test_replace_keeps_surroundings():
    text = f"top\n{BEGIN}\nold\n{END}\nbottom\n"
    assert upsert_block(text, "new\n") == f"top\n{BEGIN}\nnew\n{END}\nbottom\n"


def test_upsert_is_idempotent():
    once = upsert_block("mine\n", "hello\n")
    assert upsert_block(once, "hello\n") == once


def test_crlf_preserved():  # Review Focus 3
    text = "mine\r\nmore\r\n"
    out = upsert_block(text, "hello\nworld\n")
    assert out.startswith("mine\r\nmore\r\n")
    assert "\n" not in out.replace("\r\n", "")
    assert ensure_line(text, "@AGENTS.md") == "mine\r\nmore\r\n@AGENTS.md\r\n"


@pytest.mark.parametrize(
    "text", [f"a\n{BEGIN}\nb\n", f"a\n{END}\nb\n", f"{END}\nx\n{BEGIN}\n"]
)
def test_unbalanced_markers_raise(text: str):  # Review Focus 4
    with pytest.raises(BlockError):
        upsert_block(text, "x\n")


def test_remove_block():
    text = f"top\n\n{BEGIN}\nold\n{END}\nbottom\n"
    assert remove_block(text) == "top\nbottom\n"


def test_remove_undoes_upsert():
    original = "# Agents\n\nmine\n"
    assert remove_block(upsert_block(original, "hello\n")) == original


def test_ensure_and_remove_line():
    text = "mine\n"
    added = ensure_line(text, "@AGENTS.md")
    assert added == "mine\n@AGENTS.md\n"
    assert ensure_line(added, "@AGENTS.md") == added
    assert remove_line(added, "@AGENTS.md") == text
    assert ensure_line("no newline", "x") == "no newline\nx\n"
