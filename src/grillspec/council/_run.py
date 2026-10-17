"""Ask every external member in parallel and collect what each answered."""

from __future__ import annotations

import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from grillspec.config import parse_member

from ._contract import extract_contract
from ._proc import Finished, killing_on_exit, run_tree
from ._prompt import CouncilError
from ._vendors import auth_state, build_argv, parse_answer, resolve_cli

if TYPE_CHECKING:
    from collections.abc import Sequence

    from grillspec.config import Member

RAW_LIMIT = 65_536
TRUNCATED = "…[truncated]"
_GEMINI_AUTH_EXIT = 41


@dataclass(frozen=True)
class MemberResult:
    """What one external member answered.

    Attributes:
        name: str - The member as configured, such as ``cli:codex@gpt-5``.
        model: str | None - The model that answered, when known.
        ok: bool - The CLI ran and exited cleanly.
        ms: int - Wall time of the call in milliseconds.
        parsed: dict[str, object] | None - The answer contract, when found.
        raw: str - The answer text, capped at 65 536 characters.
        error: str | None - Why the member gave no answer.

    """

    name: str
    model: str | None
    ok: bool
    ms: int
    parsed: dict[str, object] | None
    raw: str
    error: str | None

    def to_json(self) -> dict[str, object]:
        """Return the result as a JSON-ready object.

        Returns:
            dict[str, object] - The fields by name.

        """
        return {
            "name": self.name,
            "model": self.model,
            "ok": self.ok,
            "ms": self.ms,
            "parsed": self.parsed,
            "raw": self.raw,
            "error": self.error,
        }


def member_spec(member: Member) -> str:
    """Write a member back in its configured form.

    Args:
        member: Member - The member.

    Returns:
        str - ``<kind>:<name>`` plus ``@<model>`` when set.

    """
    suffix = f"@{member.model}" if member.model else ""
    return f"{member.kind}:{member.name}{suffix}"


def _cap(text: str) -> str:
    """Cap an answer so one runaway member cannot flood the grilling agent.

    Args:
        text: str - The answer.

    Returns:
        str - At most 65 536 characters, marked when cut.

    """
    return text if len(text) <= RAW_LIMIT else text[:RAW_LIMIT] + TRUNCATED


def _last_line(text: str) -> str:
    """Return the last non-empty line, where CLIs put their final error.

    Args:
        text: str - Output.

    Returns:
        str - The line, or an empty string.

    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _failed(member: Member, error: str, *, ms: int = 0, raw: str = "") -> MemberResult:
    """Build the result of a member that gave no answer.

    Returns:
        MemberResult - ``ok`` False with the error.

    """
    return MemberResult(
        name=member_spec(member),
        model=member.model,
        ok=False,
        ms=ms,
        parsed=None,
        raw=raw,
        error=error,
    )


def _exit_error(member: Member, done: Finished, timeout: int) -> str | None:
    """Explain a run that did not end cleanly.

    Args:
        member: Member - The member.
        done: Finished - What its process left.
        timeout: int - The timeout it ran under.

    Returns:
        str | None - The error, or None for a clean exit.

    """
    if done.returncode is None:
        return f"timeout after {timeout}s"
    if done.returncode == 0:
        return None
    if member.name == "gemini" and done.returncode == _GEMINI_AUTH_EXIT:
        return "not authenticated"
    line = _last_line(done.stderr.decode("utf-8", "replace"))
    return f"exit {done.returncode}: {line}" if line else f"exit {done.returncode}"


def _judge(member: Member, done: Finished, *, ms: int, timeout: int) -> MemberResult:
    """Turn a finished run into the member's result.

    Args:
        member: Member - The member.
        done: Finished - What its process left.
        ms: int - Wall time in milliseconds.
        timeout: int - The timeout it ran under.

    Returns:
        MemberResult - The answer, or why there is none.

    """
    stdout = done.stdout.decode("utf-8", "replace")
    failure = _exit_error(member, done, timeout)
    if failure is not None:
        return _failed(member, failure, ms=ms, raw=_cap(stdout))
    text, model, error = parse_answer(member.name, stdout)
    raw = _cap(text)
    if error is not None:
        return _failed(member, error, ms=ms, raw=raw)
    return MemberResult(
        name=member_spec(member),
        model=model or member.model,
        ok=True,
        ms=ms,
        parsed=extract_contract(raw),
        raw=raw,
        error=None,
    )


def _ask(
    member: Member, prompt: str, timeout: int, project_root: Path | None
) -> MemberResult:
    """Ask one member, in the project or a fresh empty temporary directory.

    Args:
        member: Member - A ``cli:`` member.
        prompt: str - The rendered prompt, sent on stdin.
        timeout: int - Seconds before its process tree is killed.
        project_root: Path | None - Where to run; None for a temporary directory.

    Returns:
        MemberResult - What it answered, or why it did not.

    """
    executable = resolve_cli(member.name)
    if executable is None:
        return _failed(member, "not installed")
    if auth_state(member.name, executable) is False:
        return _failed(member, "not authenticated")
    argv = build_argv(member, executable)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(
        prefix="grillspec-council-", ignore_cleanup_errors=True
    ) as scratch:
        try:
            done = run_tree(
                argv,
                stdin=prompt.encode(),
                timeout=timeout,
                cwd=project_root or Path(scratch),
            )
        except OSError as error:
            return _failed(member, f"cannot start: {error}")
    ms = int((time.monotonic() - started) * 1000)
    return _judge(member, done, ms=ms, timeout=timeout)


def run_members(
    members: Sequence[Member],
    prompt: str,
    *,
    timeout: int,
    project_root: Path | None,
) -> list[MemberResult]:
    """Ask every external member at once.

    Args:
        members: Sequence[Member] - ``cli:`` members.
        prompt: str - The rendered prompt.
        timeout: int - Seconds each member may take.
        project_root: Path | None - Run in the project; None for a fresh empty
            temporary directory per member.

    Returns:
        list[MemberResult] - One result per member, in the given order.

    """
    if not members:
        return []
    with killing_on_exit(), ThreadPoolExecutor(max_workers=len(members)) as pool:
        futures = [
            pool.submit(_ask, member, prompt, timeout, project_root)
            for member in members
        ]
        return [future.result() for future in futures]


def resolve_members(flag: str | None, configured: Sequence[str]) -> list[Member]:
    """Pick the external members for one council call.

    Args:
        flag: str | None - Comma-separated members from ``--members``; None to
            use the configuration.
        configured: Sequence[str] - ``council.members`` from the configuration;
            its role members are skipped, since they run as subagents.

    Returns:
        list[Member] - ``cli:`` members, duplicates dropped, first kept.

    Raises:
        CouncilError: If an entry is invalid, ``--members`` names a role, or no
            external member is left.

    """
    entries = (
        [item.strip() for item in flag.split(",") if item.strip()]
        if flag is not None
        else list(configured)
    )
    chosen: dict[str, Member] = {}
    for entry in entries:
        try:
            member = parse_member(entry)
        except ValueError as error:
            raise CouncilError(str(error)) from None
        if member.kind == "role":
            if flag is not None:
                msg = (
                    f"{entry}: role members run as subagents, not through this command"
                )
                raise CouncilError(msg)
            continue
        _ = chosen.setdefault(member_spec(member), member)
    if not chosen:
        msg = "no external council members (role members run as subagents)"
        raise CouncilError(msg)
    return list(chosen.values())
