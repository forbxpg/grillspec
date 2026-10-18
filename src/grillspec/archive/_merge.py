"""Apply an OpenSpec change's deltas to its living specs, in memory first."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import NoReturn

from grillspec.markdown import numbered_outside

_BREAK = re.compile(r"(\r\n|\r|\n)")
_REQ = re.compile(r"^### Requirement:\s*(.*?)\s*$")
_SECTION = re.compile(r"^## (?!#)(.+?)\s*$")
_HEADING = re.compile(r"^#### (?!#)\s*(?:Scenario:)?\s*(.*?)\s*$")
_RENAME = re.compile(
    r"^\s*[-*]?\s*(FROM|TO):\s*`?\s*#{0,3}\s*(?:Requirement:)?\s*(.*?)\s*`?\s*$"
)
DELTAS = ("RENAMED", "REMOVED", "MODIFIED", "ADDED")


class MergeError(Exception):
    """A delta cannot be applied; nothing is written."""


@dataclass
class Blocks:
    """A spec split around its requirement blocks.

    Attributes:
        head: list[str] - Lines before the first requirement of the section.
        blocks: list[tuple[str, list[str]]] - (name, lines) per requirement.
        tail: list[str] - Lines after the requirements section.
        newline: str - The file's newline sequence.

    """

    head: list[str]
    blocks: list[tuple[str, list[str]]] = field(default_factory=list)
    tail: list[str] = field(default_factory=list)
    newline: str = "\n"

    def render(self) -> str:
        """Join the spec back into text.

        Returns:
            str - The spec, with its newline sequence and a final newline.

        """
        lines = [
            *self.head,
            *(line for _, block in self.blocks for line in block),
            *self.tail,
        ]
        while lines and not lines[-1].strip():
            _ = lines.pop()
        return self.newline.join(lines) + self.newline


def _split(text: str) -> tuple[list[str], str]:
    """Split text into lines, keeping its newline style.

    Args:
        text: str - File text.

    Returns:
        tuple[list[str], str] - Lines and the newline sequence.

    """
    newline = "\r\n" if "\r\n" in text else "\n"
    return _BREAK.split(text)[::2], newline


def _sections(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Find each ``## `` section's line range, ignoring fenced lines.

    Args:
        lines: list[str] - File lines.

    Returns:
        dict[str, tuple[int, int]] - Title to (first body index, end index).

    """
    starts = [
        (n - 1, m.group(1))
        for n, text in numbered_outside(lines)
        if (m := _SECTION.match(text))
    ]
    ranges: dict[str, tuple[int, int]] = {}
    for i, (start, title) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(lines)
        ranges[title] = (start + 1, end)
    return ranges


def _blocks(
    lines: list[str], start: int, end: int
) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Cut a section's body into the lines before the first block and the blocks.

    Args:
        lines: list[str] - File lines.
        start: int - First body index.
        end: int - End index.

    Returns:
        tuple[list[str], list[tuple[str, list[str]]]] - Leading lines and blocks.

    """
    outside = {n - 1 for n, _ in numbered_outside(lines)}
    lead: list[str] = []
    blocks: list[tuple[str, list[str]]] = []
    for i in range(start, end):
        match = _REQ.match(lines[i]) if i in outside else None
        if match:
            blocks.append((match.group(1), [lines[i]]))
        elif blocks:
            blocks[-1][1].append(lines[i])
        else:
            lead.append(lines[i])
    return lead, blocks


def parse_living(text: str) -> Blocks:
    """Split a living spec around the blocks of its ``## Requirements`` section.

    Args:
        text: str - Spec text.

    Returns:
        Blocks - Head (through the section's lead lines), blocks and tail.

    Raises:
        MergeError: If the spec has no ``## Requirements`` section.

    """
    lines, newline = _split(text.removeprefix("﻿"))
    ranges = _sections(lines)
    if "Requirements" not in ranges:
        msg = "living spec has no '## Requirements' section"
        raise MergeError(msg)
    start, end = ranges["Requirements"]
    lead, blocks = _blocks(lines, start, end)
    return Blocks([*lines[:start], *lead], blocks, lines[end:], newline)


def parse_delta(
    text: str,
) -> tuple[dict[str, list[tuple[str, list[str]]]], list[tuple[str, str]], str]:
    """Read a delta file's operations.

    Args:
        text: str - Delta spec text.

    Returns:
        tuple - Blocks per delta section, RENAMED (from, to) pairs, and the
            ``## Purpose`` body ("" when absent).

    """
    lines, _ = _split(text.removeprefix("﻿"))
    ranges = _sections(lines)
    found: dict[str, list[tuple[str, list[str]]]] = {}
    for kind in ("REMOVED", "MODIFIED", "ADDED"):
        if f"{kind} Requirements" in ranges:
            found[kind] = _blocks(lines, *ranges[f"{kind} Requirements"])[1]
    renames: list[tuple[str, str]] = []
    if "RENAMED Requirements" in ranges:
        old: str | None = None
        for line in lines[slice(*ranges["RENAMED Requirements"])]:
            match = _RENAME.match(line)
            if not match:
                continue
            if match.group(1) == "FROM":
                old = match.group(2)
            elif old is not None:
                renames.append((old, match.group(2)))
                old = None
    purpose = ""
    if "Purpose" in ranges:
        purpose = "\n".join(lines[slice(*ranges["Purpose"])]).strip()
    return found, renames, purpose


def _headings(block: list[str]) -> Counter[str]:
    """Count the level-4 headings of a requirement block, outside fences.

    Args:
        block: list[str] - Block lines.

    Returns:
        Counter[str] - Trimmed heading text (without ``Scenario:``) per occurrence.

    """
    return Counter(
        m.group(1) for _, line in numbered_outside(block) if (m := _HEADING.match(line))
    )


def _ensure_blank(block: list[str]) -> list[str]:
    """End a block with exactly one blank line so blocks stay separated.

    Args:
        block: list[str] - Block lines.

    Returns:
        list[str] - The block with one trailing blank line.

    """
    trimmed = list(block)
    while trimmed and not trimmed[-1].strip():
        _ = trimmed.pop()
    return [*trimmed, ""]


@dataclass
class _Merge:
    """The living spec's blocks while deltas are applied to them."""

    capability: str
    names: list[str]
    blocks: dict[str, list[str]]
    ops: list[str] = field(default_factory=list)

    def refuse(self, detail: str) -> NoReturn:
        """Refuse an operation; the caller writes nothing.

        Args:
            detail: str - What is wrong.

        Raises:
            MergeError: Always, naming the capability.

        """
        msg = f"{self.capability}: {detail}"
        raise MergeError(msg)

    def rename(self, old: str, new: str) -> None:
        """Rename a requirement, keeping its text and position."""
        if old not in self.blocks:
            self.refuse(f"RENAMED source '{old}' is not in the living spec")
        if new in self.blocks:
            self.refuse(f"RENAMED target '{new}' already exists")
        lines = list(self.blocks.pop(old))
        lines[0] = f"### Requirement: {new}"
        self.blocks[new] = lines
        self.names[self.names.index(old)] = new
        self.ops.append(f"{self.capability}: rename '{old}' → '{new}'")

    def remove(self, name: str) -> None:
        """Remove a requirement; a missing one only warns, as in OpenSpec."""
        if name not in self.blocks:
            self.ops.append(f"{self.capability}: warning: REMOVED '{name}' is gone")
            return
        del self.blocks[name]
        self.names.remove(name)
        self.ops.append(f"{self.capability}: remove '{name}'")

    def modify(self, name: str, block: list[str]) -> None:
        """Replace a requirement, refusing when a living heading would be lost."""
        if name not in self.blocks:
            self.refuse(f"MODIFIED '{name}' is not in the living spec")
        missing = sorted((_headings(self.blocks[name]) - _headings(block)).keys())
        if missing:
            lost = ", ".join(f"'{m}'" for m in missing)
            self.refuse(f"MODIFIED '{name}' drops heading(s) {lost}")
        self.blocks[name] = _ensure_blank(block)
        self.ops.append(f"{self.capability}: modify '{name}'")

    def add(self, name: str, block: list[str]) -> None:
        """Append a requirement."""
        if name in self.blocks:
            self.refuse(f"ADDED '{name}' already exists")
        self.blocks[name] = _ensure_blank(block)
        self.names.append(name)
        self.ops.append(f"{self.capability}: add '{name}'")


def apply_delta(
    living: Blocks,
    delta: dict[str, list[tuple[str, list[str]]]],
    renames: list[tuple[str, str]],
    capability: str,
) -> tuple[Blocks, list[str]]:
    """Apply one capability's deltas: RENAMED, REMOVED, MODIFIED, then ADDED.

    Args:
        living: Blocks - The living spec.
        delta: dict - Delta blocks per kind.
        renames: list[tuple[str, str]] - RENAMED pairs.
        capability: str - Capability path, for messages.

    Returns:
        tuple[Blocks, list[str]] - The new spec and one line per operation.

    Raises:
        MergeError: If the living spec repeats a requirement name, or a delta
            cannot be applied.

    """
    repeated = sorted(
        n for n, k in Counter(n for n, _ in living.blocks).items() if k > 1
    )
    if repeated:
        names = ", ".join(f"'{n}'" for n in repeated)
        msg = f"{capability}: the living spec repeats requirement(s) {names}"
        raise MergeError(msg)
    merge = _Merge(capability, [n for n, _ in living.blocks], dict(living.blocks))
    for old, new in renames:
        merge.rename(old, new)
    for name, _ in delta.get("REMOVED", []):
        merge.remove(name)
    for name, block in delta.get("MODIFIED", []):
        merge.modify(name, block)
    for name, block in delta.get("ADDED", []):
        merge.add(name, block)
    ordered = [(name, _ensure_blank(merge.blocks[name])) for name in merge.names]
    return Blocks(living.head, ordered, living.tail, living.newline), merge.ops


def new_spec(capability: str, purpose: str, change_id: str) -> Blocks:
    """Start a living spec for a new capability.

    Args:
        capability: str - Capability path.
        purpose: str - The delta's Purpose ("" for none).
        change_id: str - The change, for OpenSpec's placeholder Purpose.

    Returns:
        Blocks - A spec with a title, Purpose and an empty Requirements section.

    """
    placeholder = f"TBD - created by archiving change {change_id}."
    text = purpose or f"{placeholder} Update Purpose after archive."
    head = [
        f"# {capability} Specification",
        "",
        "## Purpose",
        "",
        text,
        "",
        "## Requirements",
        "",
    ]
    return Blocks(head)
