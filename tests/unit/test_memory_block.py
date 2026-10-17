"""Tests for the memory block in AGENTS.md (spec S5-R1, S5-R2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grillspec.blocks import BEGIN, END, remove_block
from grillspec.config import Backend
from grillspec.init import init_project
from grillspec.memory import (
    MEMORY_BEGIN,
    MEMORY_END,
    Entry,
    MemoryBlockError,
    add_entry,
    read_entries,
    retire_entry,
)
from grillspec.paths import template
from support import write

if TYPE_CHECKING:
    from pathlib import Path

ROUTER = f"{BEGIN}\nrouter\n{END}\n"
MEMORY = (
    f"{MEMORY_BEGIN}\n## Project memory (grillspec)\n"
    "- [command] Run tests with uv run pytest (add-x)\n"
    "- [gotcha] Windows needs .cmd shims (add-y)\n"
    f"{MEMORY_END}\n"
)
TESTS = Entry("command", "Run tests with uv run pytest", "add-x")


def _memory_part(text: str) -> str:
    start = text.index(MEMORY_BEGIN)
    return text[start : text.index(MEMORY_END) + len(MEMORY_END)]


def test_init_keeps_memory(tmp_path: Path):  # S5-R1-S1
    agents = write(tmp_path / "AGENTS.md", f"# Project\n\n{ROUTER}\n{MEMORY}")
    before = _memory_part(agents.read_text(encoding="utf-8"))
    _ = init_project(tmp_path, Backend.SUPERPOWERS)
    _ = init_project(tmp_path, Backend.SUPERPOWERS)
    after = agents.read_text(encoding="utf-8")
    assert _memory_part(after) == before
    assert template("agents-block.md").strip() in after


def test_router_removal_keeps_memory():  # S5-R1-S2
    text = f"{ROUTER}\n{MEMORY}"
    assert _memory_part(remove_block(text)) == _memory_part(text)


def test_template_has_no_memory_heading():
    assert "### Memory" not in template("agents-block.md")


@pytest.mark.parametrize(
    "text",
    [
        f"{MEMORY_BEGIN}\n- [command] x (a)\n",
        f"- [command] x (a)\n{MEMORY_END}\n",
        f"{MEMORY_END}\n{MEMORY_BEGIN}\n",
    ],
)
def test_unbalanced_memory_markers(text: str):  # S5-R1-S3
    with pytest.raises(MemoryBlockError, match="memory markers"):
        _ = read_entries(text)
    with pytest.raises(MemoryBlockError):
        _ = add_entry(text, TESTS)


def test_add_creates_block_after_router():
    text = add_entry(f"# Project\n\n{ROUTER}\n# Notes\n", TESTS)
    assert text == (
        f"# Project\n\n{BEGIN}\nrouter\n{END}\n\n{MEMORY_BEGIN}\n"
        "## Project memory (grillspec)\n"
        "- [command] Run tests with uv run pytest (add-x)\n"
        f"{MEMORY_END}\n\n# Notes\n"
    )


def test_add_without_router_appends():
    text = add_entry("# Project\n", TESTS)
    assert text.startswith("# Project\n\n" + MEMORY_BEGIN)
    assert add_entry("", TESTS).startswith(MEMORY_BEGIN)


def test_add_appends_and_lists():
    text = add_entry(
        MEMORY, Entry("docs", "Glossary → docs/grillspec/memory/glossary.md", "c")
    )
    assert [e.category for e in read_entries(text)] == ["command", "gotcha", "docs"]
    assert read_entries(text)[2].line() == (
        "- [docs] Glossary → docs/grillspec/memory/glossary.md (c)"
    )


@pytest.mark.parametrize(
    "entry",
    [
        Entry("misc", "x", "c"),
        Entry("command", "x" * 161, "c"),
        Entry("command", "", "c"),
        Entry("command", "a\nb", "c"),
        Entry("command", f"see {MEMORY_END}", "c"),
        Entry("command", "<!-- hidden -->", "c"),
        Entry("command", "# heading", "c"),
        Entry("command", "x", "bad id"),
        Entry("command", "  RUN tests WITH uv   run pytest ", "z"),
    ],
)
def test_refusals(entry: Entry):
    with pytest.raises(MemoryBlockError):
        _ = add_entry(MEMORY, entry)


def test_cap():
    text = ""
    for n in range(40):
        text = add_entry(text, Entry("convention", f"rule {n}", "c"))
    assert len(read_entries(text)) == 40
    with pytest.raises(MemoryBlockError, match="40"):
        _ = add_entry(text, Entry("convention", "rule 40", "c"))


def test_retire_keeps_order():
    text = add_entry(MEMORY, Entry("constraint", "Never commit private/", "c"))
    left = read_entries(retire_entry(text, 2))
    assert [e.text for e in left] == [
        "Run tests with uv run pytest",
        "Never commit private/",
    ]


@pytest.mark.parametrize("number", [0, -1, 3])
def test_retire_out_of_range(number: int):
    with pytest.raises(MemoryBlockError, match="no entry"):
        _ = retire_entry(MEMORY, number)


def test_crlf_preserved():  # Review Focus 1
    text = f"# P\r\n\r\n{MEMORY}".replace("\n", "\r\n").replace("\r\r\n", "\r\n")
    added = add_entry(text, Entry("gotcha", "CRLF stays", "c"))
    assert "\n" not in added.replace("\r\n", "")
    assert added.startswith("# P\r\n\r\n")
    assert retire_entry(added, 1).count("\r\n") == added.count("\r\n") - 1


def test_foreign_line_in_block():  # Review Focus 3
    text = MEMORY.replace("- [gotcha]", "* note: [gotcha]")
    with pytest.raises(MemoryBlockError, match="line 3 of the memory block"):
        _ = read_entries(text)


def test_blank_lines_allowed_and_dropped():
    text = MEMORY.replace("(add-x)\n", "(add-x)\n\n")
    assert len(read_entries(text)) == 2
    assert "\n\n- [gotcha]" not in add_entry(text, Entry("gotcha", "new", "c"))


def test_parentheses_inside_text():
    entry = Entry("convention", "Use write_atomic() (never open(path, 'w'))", "s2")
    (stored,) = read_entries(add_entry("", entry))
    assert stored == entry
