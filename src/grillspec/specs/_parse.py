"""Read a spec's Markdown into sections, requirements, scenarios and log items."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from grillspec.config import ConfigError
from grillspec.markdown import numbered_lines_outside_fences

if TYPE_CHECKING:
    from pathlib import Path

SCENARIO_ID = re.compile(r"[A-Z]{2,4}-[1-9][0-9]*")
LOG_SECTION = "Decision log"
_SECTION = re.compile(r"^## (?!#)(.+?)\s*$")
_REQUIREMENT = re.compile(r"^### Requirement:\s*(.*?)\s*$")
_SCENARIO = re.compile(r"^#### Scenario:\s*(.*?)\s*$")
_TOP_HEADING = re.compile(r"^# ")
_LEVEL4 = re.compile(r"^#### (?!#)\s*(.*?)\s*$")
_WHEN = re.compile(r"^\s*[-*]\s+\*\*WHEN\*\*")
_THEN = re.compile(r"^\s*[-*]\s+\*\*THEN\*\*")
_LOG_ITEM = re.compile(r"^\s*[-*+] \[([ x~])\]\s+(\S+)")


@dataclass(frozen=True)
class Scenario:
    """One ``#### Scenario:`` block.

    Attributes:
        name: str - Heading text after ``Scenario:``.
        line: int - 1-based line of the heading.
        scenario_id: str | None - The leading ID such as ``RL-3``, when present.
        has_when: bool - A ``- **WHEN**`` line follows before the next heading.
        has_then: bool - A ``- **THEN**`` line follows before the next heading.
        well_formed: bool - The heading reads ``#### Scenario:``; False for any
            other level-4 heading inside a requirement.

    """

    name: str
    line: int
    scenario_id: str | None
    has_when: bool
    has_then: bool
    well_formed: bool = True


@dataclass(frozen=True)
class Requirement:
    """One ``### Requirement:`` block.

    Attributes:
        name: str - Heading text after ``Requirement:``.
        line: int - 1-based line of the heading.
        text: str - Body before the first scenario, stripped.
        scenarios: tuple[Scenario, ...] - Its scenarios, in order.
        section: str - Title of the enclosing ``## `` heading.

    """

    name: str
    line: int
    text: str
    scenarios: tuple[Scenario, ...]
    section: str


@dataclass(frozen=True)
class LogItem:
    """One checkbox item of the decision log.

    Attributes:
        item_id: str - First token after the box, such as ``Q4``.
        line: int - 1-based line.
        is_open: bool - Unchecked (``- [ ]``).
        deferred: bool - The line says ``deferred``.

    """

    item_id: str
    line: int
    is_open: bool
    deferred: bool


@dataclass(frozen=True)
class Document:
    """A parsed spec file.

    Attributes:
        path: Path - The file.
        sections: dict[str, tuple[int, str]] - ``## `` title to its heading line
            and body text up to the next ``## `` heading.
        requirements: tuple[Requirement, ...] - Requirements in file order.
        log: tuple[LogItem, ...] - Items of the ``## Decision log`` section.

    """

    path: Path
    sections: dict[str, tuple[int, str]]
    requirements: tuple[Requirement, ...]
    log: tuple[LogItem, ...]


def scenario_id(name: str) -> str | None:
    """Return a scenario name's leading ID.

    Args:
        name: str - Scenario heading text.

    Returns:
        str | None - The first token when it is an ID such as ``RL-3``.

    """
    token = name.split(maxsplit=1)[0] if name.strip() else ""
    return token if SCENARIO_ID.fullmatch(token) else None


class _Builder:
    """Collects blocks while the parser walks the lines."""

    def __init__(self) -> None:
        self.sections: dict[str, tuple[int, list[str]]] = {}
        self.requirements: list[Requirement] = []
        self.log: list[LogItem] = []
        self.section: str = ""
        self._req: tuple[str, int, list[str], list[Scenario]] | None = None
        self._scenario: tuple[str, int, bool, bool, bool] | None = None

    def close_scenario(self) -> None:
        """Finish the open scenario, if any."""
        if self._scenario is not None and self._req is not None:
            name, line, when, then, ok = self._scenario
            found = Scenario(name, line, scenario_id(name), when, then, well_formed=ok)
            self._req[3].append(found)
        self._scenario = None

    def close_requirement(self) -> None:
        """Finish the open requirement, if any."""
        self.close_scenario()
        if self._req is not None:
            name, line, body, scenarios = self._req
            text = "\n".join(body).strip()
            self.requirements.append(
                Requirement(name, line, text, tuple(scenarios), self.section)
            )
        self._req = None

    def line(self, number: int, line: str) -> None:
        """Take one line outside fences.

        Args:
            number: int - 1-based line number.
            line: str - The line.

        """
        section = _SECTION.match(line)
        if section:
            self.close_requirement()
            self.section = section.group(1)
            self.sections[self.section] = (number, [])
            return
        if self.section in self.sections:
            self.sections[self.section][1].append(line)
        self._block(number, line)

    def _inside_requirement(self, number: int, line: str) -> None:
        """Track a line inside a requirement, the way OpenSpec reads blocks.

        Only ``### Requirement:``, ``## `` and ``# `` end a requirement; every
        level-4 heading starts a scenario (a malformed one unless it reads
        ``#### Scenario:``); deeper headings stay inside the open block.

        Args:
            number: int - 1-based line number.
            line: str - The line.

        """
        scenario = _SCENARIO.match(line)
        level4 = _LEVEL4.match(line)
        if scenario or level4:
            self.close_scenario()
            name = scenario.group(1) if scenario else line.lstrip("# ").strip()
            self._scenario = (name, number, False, False, scenario is not None)
        elif self._scenario is not None:
            self._scenario = _scenario_line(self._scenario, line)
        elif self._req is not None:
            self._req[2].append(line)

    def _block(self, number: int, line: str) -> None:
        """Track requirement, scenario and log lines.

        Args:
            number: int - 1-based line number.
            line: str - The line.

        """
        requirement = _REQUIREMENT.match(line)
        if requirement:
            self.close_requirement()
            self._req = (requirement.group(1), number, [], [])
        elif _TOP_HEADING.match(line):
            self.close_requirement()
        elif self._req is not None:
            self._inside_requirement(number, line)
        item = _LOG_ITEM.match(line)
        if item and self.section == LOG_SECTION:
            mark, item_id = item.groups()
            self.log.append(LogItem(item_id, number, mark == " ", "deferred" in line))


def _scenario_line(
    scenario: tuple[str, int, bool, bool, bool], line: str
) -> tuple[str, int, bool, bool, bool]:
    """Note a WHEN or THEN line in the open scenario.

    Args:
        scenario: tuple[str, int, bool, bool, bool] - Name, line, when, then, ok.
        line: str - The line.

    Returns:
        tuple[str, int, bool, bool, bool] - The updated scenario.

    """
    name, at, when, then, ok = scenario
    return (
        name,
        at,
        when or bool(_WHEN.match(line)),
        then or bool(_THEN.match(line)),
        ok,
    )


def parse_markdown(path: Path) -> Document:
    """Parse a spec file.

    Args:
        path: Path - The file.

    Returns:
        Document - Its sections, requirements and decision-log items.

    Raises:
        ConfigError: If the file is not UTF-8.

    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        msg = f"{path}: not UTF-8 ({error}); re-save it as UTF-8"
        raise ConfigError(msg) from error
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    builder = _Builder()
    for number, line in numbered_lines_outside_fences(text):
        builder.line(number, line)
    builder.close_requirement()
    sections = {
        title: (line, "\n".join(body).strip())
        for title, (line, body) in builder.sections.items()
    }
    return Document(path, sections, tuple(builder.requirements), tuple(builder.log))
