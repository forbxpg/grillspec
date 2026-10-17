"""Helpers that drive plan execution: workspace, task briefs, done, review."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from grillspec.council import killing_on_exit, resolve_cli, run_tree
from grillspec.markdown import numbered_outside
from grillspec.paths import write_atomic
from grillspec.specs import parse_plan

WORKSPACE = Path(".grillspec") / "exec"
TAIL_LINES = 40
TEST_TIMEOUT = 3600
_GIT_TIMEOUT = 60
_GROUP = re.compile(r"^## (\d+)\. ")
_HEADING = re.compile(r"^## ")
_TASK_LINE = re.compile(r"^- \[[ xX]\] \d+\.\d+ ")
# Line breaks the plan parser knows; U+2028 and friends stay inside a line.
_BREAK = re.compile(r"(\r\n|\r|\n)")


class ExecError(Exception):
    """An execution helper cannot do what was asked.

    Attributes:
        code: int - Exit code: 1 for usage problems, 3 for a bad review range.

    """

    def __init__(self, message: str, code: int = 1) -> None:
        """Create the error.

        Args:
            message: str - One-line explanation.
            code: int - Exit code.

        """
        super().__init__(message)
        self.code: int = code


@dataclass(frozen=True)
class ExecTarget:
    """The change being executed.

    Attributes:
        root: Path - Project root.
        plan: Path - The change's plan file.
        change_id: str - The active change's id.

    """

    root: Path
    plan: Path
    change_id: str


def _git(root: Path, *args: str, strip: bool = True) -> tuple[int, str]:
    """Run git in the project.

    Args:
        root: Path - Project root.
        *args: str - Git arguments.
        strip: bool - Strip surrounding whitespace from stdout.

    Returns:
        tuple[int, str] - Exit code and stdout.

    Raises:
        ExecError: If git is not installed or does not answer in time.

    """
    git = resolve_cli("git")
    if git is None:
        msg = "git is not on PATH"
        raise ExecError(msg)
    done = run_tree([git, "-C", str(root), *args], stdin=None, timeout=_GIT_TIMEOUT)
    if done.returncode is None:
        msg = f"git {args[0]} did not answer in {_GIT_TIMEOUT}s"
        raise ExecError(msg)
    out = done.stdout.decode("utf-8", "replace")
    return done.returncode, out.strip() if strip else out.rstrip()


def workspace(root: Path, change_id: str) -> Path:
    """Create (once) and return a change's execution workspace.

    Args:
        root: Path - Project root.
        change_id: str - Active change id.

    Returns:
        Path - ``.grillspec/exec/<change-id>/``, ignored by git, with a ledger.

    """
    folder = root / WORKSPACE / change_id
    folder.mkdir(parents=True, exist_ok=True)
    ignore = folder / ".gitignore"
    if not ignore.is_file():
        write_atomic(ignore, "*\n")
    ledger = folder / "progress.md"
    if not ledger.is_file():
        write_atomic(ledger, f"# grillspec ledger — change: {change_id}\n")
    return folder


def _lines(plan: Path) -> tuple[str, list[str]]:
    """Read a plan's text and its lines, keeping its BOM and newline style.

    Args:
        plan: Path - The plan.

    Returns:
        tuple[str, list[str]] - Raw text (BOM included) and its lines, split only
            on CR/LF, the way the plan parser numbers them.

    """
    text = plan.read_bytes().decode("utf-8")
    body = text.removeprefix("\ufeff")
    return text, _BREAK.split(body)[::2]


def _task_line(root: Path, plan: Path, task: str) -> int:
    """Find a task's checkbox line.

    Args:
        root: Path - Project root.
        plan: Path - The plan.
        task: str - ``N.M``.

    Returns:
        int - 1-based line number.

    Raises:
        ExecError: If the plan has no such task.

    """
    for found in parse_plan(plan).tasks:
        if f"{found.number[0]}.{found.number[1]}" == task:
            return found.line
    where = plan.relative_to(root).as_posix()
    msg = f"no task {task} in {where}"
    raise ExecError(msg)


def start_task(target: ExecTarget, task: str) -> tuple[Path, str]:
    """Write a task's brief and report the commit its review range starts from.

    Args:
        target: ExecTarget - The change being executed.
        task: str - ``N.M``.

    Returns:
        tuple[Path, str] - The brief file and the HEAD commit (BASE).

    Raises:
        ExecError: If the repository has no commits yet.

    """
    root, plan, change_id = target.root, target.plan, target.change_id
    line = _task_line(root, plan, task)
    _, lines = _lines(plan)
    outside = dict(numbered_outside(lines))
    first_group = next(
        (n - 1 for n, text in outside.items() if _GROUP.match(text)), len(lines)
    )
    # The block ends at the next task or ## heading outside code fences.
    end = next(
        (
            n - 1
            for n, text in outside.items()
            if n > line and (_HEADING.match(text) or _TASK_LINE.match(text))
        ),
        len(lines),
    )
    header = "\n".join(lines[:first_group]).rstrip()
    block = "\n".join(lines[line - 1 : end]).rstrip()
    code, base = _git(root, "rev-parse", "--verify", "HEAD")
    if code != 0:
        msg = "the repository has no commits yet; commit before starting a task"
        raise ExecError(msg)
    brief = workspace(root, change_id) / f"task-{task}-brief.md"
    write_atomic(brief, f"{header}\n\n{block}\n")
    return brief, base


def _tick(plan: Path, line: int) -> None:
    """Tick a task's box, leaving every other byte of the plan unchanged.

    Args:
        plan: Path - The plan.
        line: int - 1-based line of the task's checkbox.

    Raises:
        ExecError: If that line is no longer the task's checkbox.

    """
    text, _ = _lines(plan)
    bom = "\ufeff" if text.startswith("\ufeff") else ""
    parts = _BREAK.split(text.removeprefix("\ufeff"))
    index = 2 * (line - 1)
    ticked = re.sub(r"^- \[ \]", "- [x]", parts[index], count=1)
    if not re.match(r"^- \[[xX]\]", ticked):
        msg = f"line {line} of {plan.name} is no longer a task checkbox"
        raise ExecError(msg)
    parts[index] = ticked
    write_atomic(plan, bom + "".join(parts))


def _executable(root: Path, command: str) -> str:
    """Resolve a test command: a path relative to the project, or a PATH name.

    Args:
        root: Path - Project root.
        command: str - The command's first word.

    Returns:
        str - The executable to run.

    Raises:
        ExecError: If it cannot be found.

    """
    if "/" in command or "\\" in command:
        path = Path(command) if Path(command).is_absolute() else root / command
        if not path.is_file():
            msg = f"cannot run {command!r}: no such file"
            raise ExecError(msg)
        return str(path)
    found = resolve_cli(command)
    if found is None:
        msg = f"cannot run {command!r}: not found on PATH"
        raise ExecError(msg)
    return found


def finish_task(
    target: ExecTarget, task: str, base: str, argv: list[str]
) -> tuple[int, str]:
    """Run a task's tests; on success tick the task and record it in the ledger.

    Args:
        target: ExecTarget - The change being executed.
        task: str - ``N.M``.
        base: str - Commit the task started from.
        argv: list[str] - Test command, run without a shell.

    Returns:
        tuple[int, str] - The command's exit code and the tail of its output.

    Raises:
        ExecError: If the task is unknown or the command cannot start.

    """
    root, plan, change_id = target.root, target.plan, target.change_id
    line = _task_line(root, plan, task)
    if not argv:
        msg = "give the test command after --"
        raise ExecError(msg)
    code, _ = _git(root, "rev-parse", "--verify", f"{base}^{{commit}}")
    if code != 0:
        msg = f"unknown commit {base}; pass the BASE that grillspec exec start printed"
        raise ExecError(msg)
    folder = workspace(root, change_id)
    executable = _executable(root, argv[0])
    try:
        with killing_on_exit():
            done = run_tree(
                [executable, *argv[1:]], stdin=None, timeout=TEST_TIMEOUT, cwd=root
            )
    except OSError as error:
        msg = f"cannot run {argv[0]!r}: {error.strerror or error}"
        raise ExecError(msg) from None
    output = (done.stdout + done.stderr).decode("utf-8", "replace")
    if done.returncode is None:
        output += f"\ngrillspec: tests timed out after {TEST_TIMEOUT}s\n"
    write_atomic(folder / f"task-{task}-output.log", output)
    tail = "\n".join(output.splitlines()[-TAIL_LINES:])
    code = 124 if done.returncode is None else done.returncode
    if code == 0:
        _tick(plan, line)
        _, head = _git(root, "rev-parse", "HEAD")
        entry = (
            f"Task {task}: complete (commits {base[:7]}..{head[:7]}, "
            f"tests: {shlex.join(argv)} → exit 0)\n"
        )
        ledger = folder / "progress.md"
        write_atomic(ledger, ledger.read_text(encoding="utf-8") + entry)
    return code, tail


def review_package(root: Path, change_id: str, base: str, head: str = "HEAD") -> Path:
    """Write the review package for a commit range.

    Args:
        root: Path - Project root.
        change_id: str - Active change id.
        base: str - First commit's parent (BASE from ``start``).
        head: str - Last commit.

    Returns:
        Path - ``review-<base7>..<head7>.diff`` in the workspace.

    Raises:
        ExecError: With code 3 when HEAD does not descend from BASE or the range
            is empty.

    """
    code, base_sha = _git(root, "rev-parse", base)
    code_head, head_sha = _git(root, "rev-parse", head)
    if code or code_head:
        msg = f"unknown commit {base if code else head}"
        raise ExecError(msg, 3)
    ancestor, _ = _git(root, "merge-base", "--is-ancestor", base_sha, head_sha)
    _, count = _git(root, "rev-list", "--count", f"{base_sha}..{head_sha}")
    if ancestor != 0 or count == "0":
        msg = f"{head} does not add commits on top of {base}"
        raise ExecError(msg, 3)
    plain = ("--no-color", "--no-ext-diff")
    results = [
        _git(root, "log", "--no-color", "--oneline", f"{base_sha}..{head_sha}"),
        _git(root, "diff", *plain, "--stat", base_sha, head_sha, strip=False),
        _git(root, "diff", *plain, "-U10", base_sha, head_sha, strip=False),
    ]
    if any(code for code, _ in results):
        msg = "git could not produce the review diff"
        raise ExecError(msg, 3)
    (_, log), (_, stat), (_, diff) = results
    path = workspace(root, change_id) / f"review-{base_sha[:7]}..{head_sha[:7]}.diff"
    write_atomic(path, f"# Commits\n{log}\n\n# Stat\n{stat}\n\n# Diff\n{diff}\n")
    return path
