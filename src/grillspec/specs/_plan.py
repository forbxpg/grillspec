"""Read a plan and check it: executable, and a valid OpenSpec tasks.md."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from grillspec.config import ConfigError
from grillspec.markdown import numbered_outside

from ._report import ERROR, WARNING, Finding
from ._rules import relative

if TYPE_CHECKING:
    from pathlib import Path

# OpenSpec 1.12 counts every line like this as a task, fenced or indented; a
# "+" bullet it ignores, but grillspec's status counts it, so it is refused too.
OPENSPEC_BOX = re.compile(r"^\s*[-*+]\s*\[([\sxX])\]\s*(.*)")
_TASK = re.compile(r"^- \[([ xX])\] (\d+)\.(\d+) (.+?)\s*$")
_VERIFY = re.compile(r"\s+[—-]\s+verify:\s*")
_GROUP = re.compile(r"^## (\d+)\. ")
_COVERS = re.compile(r"Covers:[ \t]*([^·\n]*)")
_TEST = re.compile(r"Test:[ \t]*([^·\n]+?)[ \t]*(?:·|$)", re.MULTILINE)
_STEP = re.compile(r"^\d+\.\s")
_TBD = re.compile(r"\b(TBD|TODO)\b")
TESTS = ("scenario-first", "reproduce-first", "characterization")
MAX_TASKS = 12
MAX_STEPS = 8
MAX_RATIO = 3


@dataclass(frozen=True)
class PlanTask:
    """One task: a checkbox line and the plain lines under it.

    Attributes:
        number: tuple[int, int] - ``(N, M)`` from ``N.M``.
        group: int | None - Number of the ``## N.`` group it sits under.
        title: str - Text before ``— verify:``.
        line: int - 1-based line of the checkbox.
        checked: bool - The box is ticked.
        verify: str | None - How completion is verified.
        covers: tuple[str, ...] - Scenario IDs it covers.
        test: str | None - Its test strategy.
        files: bool - It has a ``Files:`` line.
        steps: int - Number of numbered steps.

    """

    number: tuple[int, int]
    group: int | None
    title: str
    line: int
    checked: bool
    verify: str | None
    covers: tuple[str, ...]
    test: str | None
    files: bool
    steps: int


@dataclass(frozen=True)
class Plan:
    """A parsed plan.

    Attributes:
        path: Path - The file.
        tasks: tuple[PlanTask, ...] - Tasks in file order.
        groups: dict[int, int] - Group number to its heading line.
        spec_link: bool - It has a ``**Spec:**`` line.
        lines: int - Number of lines.
        bad_boxes: tuple[int, ...] - Lines OpenSpec would count as tasks that are
            not in the task form (inside fences, indented, unnumbered).
        tbd: tuple[int, ...] - Lines with TBD or TODO outside fences.

    """

    path: Path
    tasks: tuple[PlanTask, ...]
    groups: dict[int, int]
    spec_link: bool
    lines: int
    bad_boxes: tuple[int, ...]
    tbd: tuple[int, ...]


def _read(path: Path) -> str:
    """Read a plan as normalised text.

    Args:
        path: Path - The file.

    Returns:
        str - Text without a BOM, with LF line endings.

    Raises:
        ConfigError: If the file is not UTF-8.

    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        msg = f"{path}: not UTF-8 ({error}); re-save it as UTF-8"
        raise ConfigError(msg) from error
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _task(
    number: int, match: re.Match[str], group: int | None, body: list[str]
) -> PlanTask:
    """Build a task from its checkbox line and the lines under it.

    Args:
        number: int - 1-based line of the checkbox.
        match: re.Match[str] - The checkbox line's match.
        group: int | None - The enclosing group number.
        body: list[str] - Lines up to the next task or ``## `` heading.

    Returns:
        PlanTask - The task.

    """
    mark, major, minor, rest = match.groups()
    parts = _VERIFY.split(rest, maxsplit=1)
    text = "\n".join(body)
    covers_match = _COVERS.search(text)
    covers = tuple(
        item.strip()
        for item in (covers_match.group(1) if covers_match else "").split(",")
        if item.strip() and item.strip() not in {"—", "-", "none"}
    )
    test_match = _TEST.search(text)
    return PlanTask(
        number=(int(major), int(minor)),
        group=group,
        title=parts[0].strip(),
        line=number,
        checked=mark in "xX",
        verify=parts[1].strip() if len(parts) > 1 and parts[1].strip() else None,
        covers=covers,
        test=test_match.group(1).strip() if test_match else None,
        files=any(line.startswith("Files:") for line in body),
        steps=sum(1 for line in body if _STEP.match(line)),
    )


def parse_plan(path: Path) -> Plan:
    """Parse a plan file.

    Args:
        path: Path - The plan (superpowers plan or OpenSpec ``tasks.md``).

    Returns:
        Plan - Its tasks, groups and problem lines.

    """
    text = _read(path)
    raw = text.split("\n")
    # One split for both views, so line numbers always agree.
    outside = dict(numbered_outside(raw))
    tasks: list[PlanTask] = []
    groups: dict[int, int] = {}
    bad: list[int] = []
    group: int | None = None
    current: tuple[int, re.Match[str], int | None, list[str]] | None = None
    for number, line in enumerate(raw, 1):
        task = _TASK.match(line) if number in outside else None
        if OPENSPEC_BOX.match(line) and task is None:
            bad.append(number)
        if number not in outside:
            continue
        if (task or line.startswith("## ")) and current is not None:
            tasks.append(_task(*current))
            current = None
        if line.startswith("## "):
            heading = _GROUP.match(line)
            group = int(heading.group(1)) if heading else None
            if heading:
                groups[int(heading.group(1))] = number
        if task:
            current = (number, task, group, [])
        elif current is not None:
            current[3].append(line)
    if current is not None:
        tasks.append(_task(*current))
    return Plan(
        path=path,
        tasks=tuple(tasks),
        groups=groups,
        spec_link=any("**Spec:**" in line for line in outside.values()),
        lines=len(raw),
        bad_boxes=tuple(bad),
        tbd=tuple(n for n, line in outside.items() if _TBD.search(line)),
    )


def valid_test(test: str | None) -> bool:
    """Tell whether a Test value is one of the D5 strategies.

    Args:
        test: str | None - The value.

    Returns:
        bool - True for a known strategy or ``none: <reason>``.

    """
    if test is None:
        return False
    if test.startswith("none:"):
        return bool(test.removeprefix("none:").strip())
    return test in TESTS


def _numbering(plan: Plan, path: Path) -> list[Finding]:
    """Check that tasks are numbered N.1, N.2, … under their ``## N.`` group.

    Args:
        plan: Plan - The plan.
        path: Path - Its relative path.

    Returns:
        list[Finding] - One error per misnumbered task.

    """
    findings: list[Finding] = []
    expected: dict[int | None, int] = {}
    for task in plan.tasks:
        major, minor = task.number
        want = expected.get(task.group, 1)
        if task.group != major or minor != want:
            findings.append(
                Finding(
                    ERROR,
                    path,
                    task.line,
                    "plan-numbering",
                    f"task {major}.{minor} should be {task.group}.{want}"
                    if task.group is not None
                    else f"task {major}.{minor} is not under a '## {major}.' group",
                )
            )
        expected[task.group] = want + 1
    return findings


def _task_findings(task: PlanTask, ids: set[str], path: Path) -> list[Finding]:
    """Check one task's verify, Test, Files and Covers.

    Args:
        task: PlanTask - The task.
        ids: set[str] - Scenario IDs in the spec.
        path: Path - The plan's relative path.

    Returns:
        list[Finding] - Its problems.

    """
    name = f"{task.number[0]}.{task.number[1]}"
    findings: list[Finding] = []
    if task.verify is None:
        findings.append(
            Finding(
                ERROR,
                path,
                task.line,
                "plan-checkbox",
                f"task {name} needs ' — verify: <how>'",
            )
        )
    if not valid_test(task.test):
        strategies = ", ".join([*TESTS, "none: <reason>"])
        findings.append(
            Finding(
                ERROR,
                path,
                task.line,
                "plan-test",
                f"task {name} needs 'Test:' with one of {strategies}",
            )
        )
    if not task.files:
        findings.append(
            Finding(
                ERROR,
                path,
                task.line,
                "plan-files",
                f"task {name} needs a 'Files:' line",
            )
        )
    findings.extend(
        Finding(
            ERROR,
            path,
            task.line,
            "plan-covers-unknown",
            f"task {name} covers {sid}, which the spec does not have",
        )
        for sid in task.covers
        if sid not in ids
    )
    if task.steps > MAX_STEPS:
        findings.append(
            Finding(
                WARNING,
                path,
                task.line,
                "plan-steps",
                f"task {name} has {task.steps} steps; split it above {MAX_STEPS}",
            )
        )
    return findings


def plan_findings(
    plan: Plan, ids: set[str], spec_lines: int, root: Path
) -> list[Finding]:
    """Check a plan against the spec it implements.

    Args:
        plan: Plan - The plan.
        ids: set[str] - Scenario IDs in the spec.
        spec_lines: int - Total line count of the spec files.
        root: Path - Project root.

    Returns:
        list[Finding] - Errors and warnings, in file order.

    """
    path = relative(plan.path, root)
    form = "use '- [ ] N.M <title> — verify: <how>' at column 0, outside code blocks"
    findings = [
        Finding(
            ERROR,
            path,
            line,
            "plan-checkbox",
            f"OpenSpec counts this box as a task; {form}",
        )
        for line in plan.bad_boxes
    ]
    findings.extend(_numbering(plan, path))
    for task in plan.tasks:
        findings.extend(_task_findings(task, ids, path))
    tested = {
        sid
        for task in plan.tasks
        if valid_test(task.test) and not str(task.test).startswith("none")
        for sid in task.covers
    }
    findings.extend(
        Finding(
            ERROR,
            path,
            0,
            "plan-coverage",
            f"scenario {sid} is not covered by any tested task",
        )
        for sid in sorted(ids - tested)
    )
    findings.extend(
        Finding(ERROR, path, line, "plan-tbd", "replace TBD/TODO with the decision")
        for line in plan.tbd
    )
    if not plan.spec_link:
        findings.append(
            Finding(ERROR, path, 0, "plan-spec-link", "add a '**Spec:** <path>' line")
        )
    if len(plan.tasks) > MAX_TASKS:
        findings.append(
            Finding(
                WARNING,
                path,
                0,
                "plan-size",
                f"{len(plan.tasks)} tasks; consider splitting above {MAX_TASKS}",
            )
        )
    if spec_lines and plan.lines > MAX_RATIO * spec_lines:
        ratio = f"over {MAX_RATIO}x the spec's {spec_lines}"
        findings.append(
            Finding(
                WARNING,
                path,
                0,
                "plan-proportion",
                f"the plan has {plan.lines} lines, {ratio}: it may transcribe code",
            )
        )
    return findings
