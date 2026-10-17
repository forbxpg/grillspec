"""Fail when a commit message or PR description credits an AI agent for the work."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

_AGENTS = (
    r"claude|anthropic|copilot|cursor|codex|openai|chatgpt|gpt-?\d|gemini|devin|aider"
    r"|codeium|windsurf|gigacode|gigachat|qwen|sourcery|coderabbit"
)
PATTERN = re.compile(
    rf"co-authored-by:[^\n]*(?:{_AGENTS})|generated (?:with|by)\W*\[?(?:{_AGENTS})",
    re.IGNORECASE,
)


def offending(messages: Mapping[str, str]) -> list[str]:
    """Return the commits whose message carries Claude attribution.

    Args:
        messages: Mapping[str, str] - Commit SHA to full message.

    Returns:
        list[str] - Offending SHAs, in input order.

    """
    return [sha for sha, message in messages.items() if PATTERN.search(message)]


def read_messages(rev_range: str) -> dict[str, str]:
    """Read full commit messages for a revision range.

    git runs without a shell and with a fixed argument list; the only variable
    argument is the range, which may not look like an option and is placed after
    ``--end-of-options``.

    Args:
        rev_range: str - A git revision range, e.g. ``origin/main..HEAD``.

    Returns:
        dict[str, str] - Commit SHA to full message.

    Raises:
        ValueError: If the range is empty or starts with ``-``.

    """
    if not rev_range or rev_range.startswith("-"):
        msg = f"not a revision range: {rev_range!r}"
        raise ValueError(msg)
    git = shutil.which("git") or "git"
    # An argv list without a shell, and the range was checked above.
    # nosemgrep
    out = subprocess.run(
        [git, "log", "--format=%H%x00%B%x01", "--end-of-options", rev_range],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    messages: dict[str, str] = {}
    for record in out.split("\x01"):
        sha, separator, message = record.strip().partition("\x00")
        if separator:
            messages[sha] = message
    return messages


def check_text_from_stdin() -> list[str]:
    """Check text piped on stdin, such as a pull request description.

    Returns:
        list[str] - ``["stdin"]`` when the text carries attribution, else empty.

    """
    return offending({"stdin": sys.stdin.read()})


if __name__ == "__main__":
    found = (
        check_text_from_stdin()
        if sys.argv[1:] == ["--stdin"]
        else offending(read_messages(sys.argv[1]))
    )
    for sha in found:
        _ = sys.stdout.write(f"{sha}: AI attribution in the commit message\n")
    sys.exit(1 if found else 0)
