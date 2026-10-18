"""Spot shell commands that obviously write files, and where they write.

A heuristic, not a parser: it knows redirections and a list of writing commands,
and treats everything else as a read. The gate is a guardrail, not a sandbox.
"""

from __future__ import annotations

import re
import shlex
from pathlib import PurePath

from ._patch import patch_paths

_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_WRAPPERS = frozenset({"sudo", "command", "env", "nohup", "time", "exec"})
_EACH_ARG = frozenset({"mkdir", "mv", "rm", "rmdir", "tee", "touch", "unlink"})
_SKIP_FIRST = frozenset({"chmod", "chown"})
_LAST_ARG = frozenset({"cp", "ln", "install"})
_GIT_WRITERS = frozenset({
    "am",
    "apply",
    "checkout",
    "cherry-pick",
    "clean",
    "commit",
    "merge",
    "mv",
    "pull",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rm",
    "stash",
    "switch",
    "worktree",
})
_OPAQUE = frozenset({
    "add-content",
    "apply_patch",
    "clear-content",
    "copy",
    "copy-item",
    "del",
    "erase",
    "move",
    "move-item",
    "new-item",
    "out-file",
    "remove-item",
    "ren",
    "rename-item",
    "set-content",
    "set-item",
})
_SINKS = frozenset({"/dev/null", "/dev/stdout", "/dev/stderr", "nul"})


def _tokens(line: str) -> list[str]:
    """Split one line into words and operators, honouring quotes.

    Args:
        line: str - One command line.

    Returns:
        list[str] - Tokens; a plain whitespace split when the quoting is broken.

    """
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return line.split()


def _is_operator(token: str) -> bool:
    return bool(token) and all(char in "();<>|&" for char in token)


def _segments(tokens: list[str]) -> tuple[list[list[str]], list[str], str | None]:
    """Cut tokens into simple commands, pulling out redirection targets.

    Args:
        tokens: list[str] - One line's tokens.

    Returns:
        tuple - Words per simple command, redirection targets, and the
            heredoc delimiter the line opens (None for none).

    """
    segments: list[list[str]] = [[]]
    targets: list[str] = []
    heredoc: str | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        if not _is_operator(token):
            segments[-1].append(token)
        elif ">" in token or token in {"<<", "<"}:
            if segments[-1] and segments[-1][-1].isdigit():
                _ = segments[-1].pop()
            if token.startswith("<<") and following is not None:
                heredoc = following.lstrip("-")
            elif ">" in token and not token.endswith("&") and following is not None:
                targets.append(following)
            index += 1
        else:
            segments.append([])
        index += 1
    return [words for words in segments if words], targets, heredoc


def _command(words: list[str]) -> tuple[str, list[str]]:
    """Return a simple command's name and arguments, past assignments and wrappers.

    Args:
        words: list[str] - The simple command's words.

    Returns:
        tuple[str, list[str]] - Lower-case base name (no ``.exe``) and arguments.

    """
    rest = list(words)
    while rest and (_ASSIGNMENT.match(rest[0]) or rest[0] in _WRAPPERS):
        rest = rest[1:]
    if not rest:
        return "", []
    name = PurePath(rest[0].replace("\\", "/")).name.lower().removesuffix(".exe")
    return name, rest[1:]


def _in_place(args: list[str]) -> list[str] | None:
    """Return the files ``sed -i`` / ``perl -i`` edit, or None when not in place.

    Args:
        args: list[str] - The arguments of ``sed`` or ``perl``.

    Returns:
        list[str] | None - The edited files.

    """
    in_place = False
    scripted = False
    positional: list[str] = []
    skip = False
    for arg in args:
        if skip:
            skip = False
            continue
        if arg.startswith("--"):
            in_place = in_place or arg.startswith("--in-place")
            scripted = scripted or arg.startswith("--expression")
        elif arg.startswith("-") and len(arg) > 1:
            in_place = in_place or "i" in arg
            if arg[-1] in "ef":
                scripted = skip = True
        else:
            positional.append(arg)
    if not in_place:
        return None
    return positional if scripted else positional[1:]


def _writes(name: str, args: list[str]) -> tuple[list[str], bool]:
    """Return what one simple command writes.

    Args:
        name: str - Command base name.
        args: list[str] - Its arguments.

    Returns:
        tuple[list[str], bool] - Written paths, and whether it writes somewhere
            this heuristic cannot name.

    """
    positional = [arg for arg in args if not arg.startswith("-")]
    found: list[str] = []
    if name in _EACH_ARG:
        found = positional
    elif name in _SKIP_FIRST:
        found = positional[1:]
    elif name in _LAST_ARG:
        found = positional[-1:]
    elif name in {"sed", "perl"}:
        found = _in_place(args) or []
    elif name == "git":
        subcommand = next((arg for arg in positional if "=" not in arg), "")
        return [], subcommand in _GIT_WRITERS
    return found, name in _OPAQUE


def shell_targets(command: str) -> tuple[list[str], bool]:
    """Find the files a shell command obviously writes.

    Args:
        command: str - The command line, possibly several lines.

    Returns:
        tuple[list[str], bool] - Written paths (deduplicated, in order, without
            ``/dev/null`` and friends), and whether some writer's target is
            unknown (``git commit``, PowerShell cmdlets).

    """
    if "*** Begin Patch" in command:
        return patch_paths(command), False
    paths: list[str] = []
    unknown = False
    heredoc: str | None = None
    for line in command.splitlines():
        if heredoc is not None:
            if line.strip() == heredoc:
                heredoc = None
            continue
        segments, targets, heredoc = _segments(_tokens(line))
        paths.extend(targets)
        for words in segments:
            found, opaque = _writes(*_command(words))
            paths.extend(found)
            unknown = unknown or opaque
    kept = [path for path in dict.fromkeys(paths) if path.lower() not in _SINKS]
    return kept, unknown
