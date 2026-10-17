"""Rules every spec follows, whatever the backend."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ._report import ERROR, WARNING, Finding

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from ._parse import Document, Requirement

MAX_REQUIREMENT_TEXT = 500
OPEN_QUESTIONS = "Open questions"
_NORMATIVE = re.compile(r"\b(SHALL|MUST)\b")
# Delta sections whose requirements carry no new behaviour to check.
_NO_BEHAVIOUR = frozenset({"REMOVED Requirements", "RENAMED Requirements"})


def relative(path: Path, root: Path) -> Path:
    """Return a path relative to the project root when it lies inside it.

    Args:
        path: Path - A file.
        root: Path - Project root.

    Returns:
        Path - The relative path, or the path itself.

    """
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _requirement(req: Requirement, path: Path) -> Iterable[Finding]:
    """Check one requirement and its scenarios.

    Args:
        req: Requirement - The requirement.
        path: Path - Its file, relative to the root.

    Yields:
        Finding - Each problem.

    """
    if not _NORMATIVE.search(req.text):
        yield Finding(
            ERROR,
            path,
            req.line,
            "requirement-shall",
            f"{req.name!r} has no SHALL or MUST",
        )
    if len(req.text) > MAX_REQUIREMENT_TEXT:
        yield Finding(
            WARNING,
            path,
            req.line,
            "requirement-length",
            f"{req.name!r} is over {MAX_REQUIREMENT_TEXT} characters; split it",
        )
    if not req.scenarios:
        yield Finding(
            ERROR,
            path,
            req.line,
            "requirement-scenario",
            f"{req.name!r} needs at least one '#### Scenario:'",
        )
    for scenario in req.scenarios:
        if not scenario.well_formed:
            expected = "'#### Scenario: <ID> <name>'"
            yield Finding(
                ERROR,
                path,
                scenario.line,
                "scenario-format",
                f"'#### {scenario.name}' inside {req.name!r} must read {expected}",
            )
            continue
        if scenario.scenario_id is None:
            yield Finding(
                ERROR,
                path,
                scenario.line,
                "scenario-id",
                f"{scenario.name!r}: start the scenario name with an ID like RL-1",
            )
        if not (scenario.has_when and scenario.has_then):
            yield Finding(
                ERROR,
                path,
                scenario.line,
                "scenario-when-then",
                f"{scenario.name!r} needs a '- **WHEN**' and a '- **THEN**' line",
            )


def requirement_findings(doc: Document, root: Path) -> list[Finding]:
    """Check every requirement that describes behaviour.

    Args:
        doc: Document - A spec or delta file.
        root: Path - Project root.

    Returns:
        list[Finding] - Problems, in file order.

    """
    path = relative(doc.path, root)
    findings: list[Finding] = []
    for req in doc.requirements:
        if req.section not in _NO_BEHAVIOUR:
            findings.extend(_requirement(req, path))
    return findings


def duplicate_ids(docs: Sequence[Document], root: Path) -> list[Finding]:
    """Find scenario IDs used twice within one change.

    Args:
        docs: Sequence[Document] - Every spec file of the change.
        root: Path - Project root.

    Returns:
        list[Finding] - One error per repeated use.

    """
    seen: dict[str, tuple[Path, int]] = {}
    findings: list[Finding] = []
    for doc in docs:
        path = relative(doc.path, root)
        for req in doc.requirements:
            for scenario in req.scenarios:
                scenario_id = scenario.scenario_id
                if scenario_id is None:
                    continue
                if scenario_id in seen:
                    first, line = seen[scenario_id]
                    where = f"{first.as_posix()}:{line}"
                    findings.append(
                        Finding(
                            ERROR,
                            path,
                            scenario.line,
                            "scenario-id-duplicate",
                            f"{scenario_id} is already used at {where}",
                        )
                    )
                else:
                    seen[scenario_id] = (path, scenario.line)
    return findings


def log_findings(log: Document, questions: Document, root: Path) -> list[Finding]:
    """Check that only deferred items stay open and that each is an open question.

    Args:
        log: Document - The file holding the decision log.
        questions: Document - The file holding ``## Open questions``.
        root: Path - Project root.

    Returns:
        list[Finding] - Problems, in log order.

    """
    path = relative(log.path, root)
    listed = questions.sections.get(OPEN_QUESTIONS, (0, ""))[1]
    findings: list[Finding] = []
    for item in log.log:
        if not item.is_open:
            continue
        if not item.deferred:
            findings.append(
                Finding(
                    ERROR,
                    path,
                    item.line,
                    "log-open-item",
                    f"{item.item_id} is still open: decide it or mark it deferred",
                )
            )
        elif not re.search(rf"(?<![\w-]){re.escape(item.item_id)}(?![\w-])", listed):
            where = relative(questions.path, root).as_posix()
            section = f"'## {OPEN_QUESTIONS}'"
            findings.append(
                Finding(
                    ERROR,
                    path,
                    item.line,
                    "deferred-not-listed",
                    f"deferred {item.item_id} is missing from {section} in {where}",
                )
            )
    return findings


def missing_sections(
    doc: Document | None, path: Path, titles: Sequence[str]
) -> list[Finding]:
    """Report required ``## `` sections that a file lacks.

    Args:
        doc: Document | None - The parsed file; None when it does not exist.
        path: Path - The file, relative to the root.
        titles: Sequence[str] - Required section titles.

    Returns:
        list[Finding] - One error per missing section (or one for a missing file).

    """
    if doc is None:
        return [Finding(ERROR, path, 0, "section-missing", "file not found")]
    return [
        Finding(ERROR, path, 0, "section-missing", f"'## {title}' is missing")
        for title in titles
        if title not in doc.sections
    ]
