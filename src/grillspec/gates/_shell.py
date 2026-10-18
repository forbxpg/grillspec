"""Spot shell commands that obviously write files, and where they write.

A heuristic, not a parser: it knows redirections and a list of writing commands,
and treats everything else as a read. The gate is a guardrail, not a sandbox.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import PurePath

from ._patch import patch_paths

_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_WRAPPERS = frozenset({"sudo", "command", "env", "nohup", "time", "exec"})
_EACH_ARG = frozenset({"mkdir", "mv", "rm", "rmdir", "tee", "touch", "unlink"})
_SKIP_FIRST = frozenset({"chmod", "chown"})
_LAST_ARG = frozenset({"cp", "ln", "install"})
_VALUE_OPTIONS = {
    "mkdir": frozenset({"-m", "--mode"}),
    "install": frozenset({"-m", "-o", "-g", "--mode", "--owner", "--group"}),
    "touch": frozenset({"-d", "-r", "-t"}),
}
_GIT_GLOBAL_VALUES = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
_GIT_WRITERS = frozenset({
    "am",
    "apply",
    "cherry-pick",
    "clean",
    "mv",
    "restore",
    "revert",
    "rm",
})
_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "pwsh", "powershell"})
_PS_ALIASES = {
    "ac": "add-content",
    "copy": "copy-item",
    "cpi": "copy-item",
    "del": "remove-item",
    "erase": "remove-item",
    "mi": "move-item",
    "move": "move-item",
    "ni": "new-item",
    "ren": "rename-item",
    "ri": "remove-item",
    "rni": "rename-item",
}
_PS_WRITERS = frozenset({
    "add-content",
    "clear-content",
    "copy-item",
    "move-item",
    "new-item",
    "out-file",
    "remove-item",
    "rename-item",
    "set-content",
    "set-item",
})
_PS_PATHS = frozenset({"-path", "-literalpath", "-filepath", "-destination"})
_PS_VALUES = frozenset({
    "-encoding",
    "-exclude",
    "-filter",
    "-include",
    "-inputobject",
    "-itemtype",
    "-name",
    "-newname",
    "-type",
    "-value",
})
_SINKS = frozenset({"/dev/null", "/dev/stdout", "/dev/stderr", "nul", "$null"})
_PATCH_BEGIN = "*** Begin Patch"
_PATCH_END = "*** End Patch"


@dataclass
class _Scan:
    """What a command writes, as found so far.

    Attributes:
        paths: list[str] - Written paths, joined with any ``cd`` target.
        unknown: bool - Some writer's target cannot be named.
        pause: bool - The command runs ``grillspec gate pause``.
        base: str - The directory a leading ``cd`` moved to ("" for none).

    """

    paths: list[str] = field(default_factory=list)
    unknown: bool = False
    pause: bool = False
    base: str = ""

    def add(self, path: str) -> None:
        """Record a written path, relative to the current ``cd`` base."""
        if not path:
            return
        if self.base and not PurePath(path).is_absolute() and path[0] not in "~$":
            path = str(PurePath(self.base) / path)
        self.paths.append(path)


def _lex(line: str) -> list[str] | None:
    """Split a logical line into tokens, keeping quotes on quoted words.

    Args:
        line: str - One logical command line.

    Returns:
        list[str] | None - Tokens, or None while a quote is still open.

    """
    lexer = shlex.shlex(line, posix=False, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def _unquote(token: str) -> str:
    return token.replace('"', "").replace("'", "")


def _is_operator(token: str) -> bool:
    return bool(token) and all(char in "();<>|&" for char in token)


def _segments(
    tokens: list[str],
) -> tuple[list[tuple[list[str], list[str]]], str | None]:
    """Cut tokens into simple commands, each with its redirection targets.

    Args:
        tokens: list[str] - One logical line's tokens.

    Returns:
        tuple - (words, redirection targets) per simple command, and the heredoc
            delimiter the line opens (None for none).

    """
    segments: list[tuple[list[str], list[str]]] = [([], [])]
    heredoc: str | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        words, targets = segments[-1]
        if not _is_operator(token):
            words.append(_unquote(token))
        elif ">" in token or token in {"<<", "<"}:
            if words and words[-1].isdigit():
                _ = words.pop()
            if following is not None:
                target = _unquote(following)
                if token.startswith("<<"):
                    heredoc = target.lstrip("-")
                elif ">" in token and not (
                    token.endswith("&") and (target.isdigit() or target == "-")
                ):
                    targets.append(target)
            index += 1
        else:
            segments.append(([], []))
        index += 1
    return [s for s in segments if s[0] or s[1]], heredoc


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


def _positional(name: str, args: list[str]) -> list[str]:
    """Return a command's non-option arguments, skipping option values.

    Args:
        name: str - Command base name.
        args: list[str] - Its arguments.

    Returns:
        list[str] - Positional arguments.

    """
    values = _VALUE_OPTIONS.get(name, frozenset())
    positional: list[str] = []
    skip = False
    for arg in args:
        if skip:
            skip = False
        elif arg in values:
            skip = True
        elif not arg.startswith("-"):
            positional.append(arg)
    return positional


def _in_place(args: list[str]) -> list[str]:
    """Return the files ``sed -i`` / ``perl -i`` edit in place.

    Args:
        args: list[str] - The arguments of ``sed`` or ``perl``.

    Returns:
        list[str] - The edited files; none when it does not edit in place.

    """
    in_place = scripted = skip = False
    positional: list[str] = []
    for arg in args:
        if skip:
            skip = False
        elif arg.startswith("--"):
            in_place = in_place or arg.startswith("--in-place")
            scripted = scripted or arg.startswith("--expression")
        elif arg.startswith(("-M", "-I", "-m")) and len(arg) > 2:  # ruff: ignore[magic-value-comparison] - perl -Mmod
            continue
        elif arg.startswith("-") and len(arg) > 1:
            in_place = in_place or "i" in arg
            if arg[-1] in "ef":
                scripted = skip = True
        elif arg:  # BSD ``sed -i ''`` leaves an empty suffix argument
            positional.append(arg)
    if not in_place:
        return []
    return positional if scripted else positional[1:]


def _git_writes(args: list[str]) -> bool:
    """Tell whether a git command changes files in the working tree.

    Args:
        args: list[str] - Arguments after ``git``.

    Returns:
        bool - True for restore, apply, clean, ``checkout --``, ``reset --hard``,
            and ``stash`` other than ``list``/``show``.

    """
    rest = list(args)
    while rest and rest[0].startswith("-"):
        option = rest.pop(0)
        if option in _GIT_GLOBAL_VALUES and rest:
            _ = rest.pop(0)
    if not rest:
        return False
    sub, more = rest[0], rest[1:]
    if sub == "checkout":
        return "--" in more
    if sub == "reset":
        return "--hard" in more
    if sub == "stash":
        return not more or more[0] not in {"list", "show"}
    return sub in _GIT_WRITERS


def _powershell(name: str, args: list[str]) -> list[str]:
    """Return the paths a PowerShell file cmdlet writes.

    Args:
        name: str - Cmdlet name, lower case, aliases resolved.
        args: list[str] - Its arguments.

    Returns:
        list[str] - Written paths.

    """
    named: list[tuple[str, str]] = []
    positional: list[str] = []
    pending: str | None = None
    for arg in args:
        lower = arg.lower()
        if pending is not None:
            if pending in _PS_PATHS:
                named.append((pending, arg))
            pending = None
        elif lower in _PS_PATHS or lower in _PS_VALUES:
            pending = lower
        elif not arg.startswith("-"):
            positional.append(arg)
    if name == "copy-item":
        dest = [value for option, value in named if option == "-destination"]
        return dest or positional[1:]
    return [value for _, value in named] + positional


def _writes(scan: _Scan, name: str, args: list[str], *, patched: bool) -> None:
    """Record what one simple command writes.

    Args:
        scan: _Scan - Findings so far.
        name: str - Command base name.
        args: list[str] - Its arguments.
        patched: bool - The command carries a Codex patch.

    """
    name = _PS_ALIASES.get(name, name)
    positional = _positional(name, args)
    found: list[str] = []
    if name in _EACH_ARG:
        found = positional
    elif name in _SKIP_FIRST:
        found = positional[1:]
    elif name in _LAST_ARG:
        found = positional[-1:]
    elif name in {"sed", "perl"}:
        found = _in_place(args)
    elif name in _PS_WRITERS:
        found = _powershell(name, args)
    elif name == "git":
        scan.unknown = scan.unknown or _git_writes(args)
    elif name == "apply_patch":
        scan.unknown = scan.unknown or not patched
    for path in found:
        scan.add(path)


def _pause(words: list[str]) -> bool:
    """Tell whether a simple command runs ``grillspec gate pause``.

    Args:
        words: list[str] - Unquoted words.

    Returns:
        bool - True when a ``grillspec`` word is followed by ``gate pause``.

    """
    for index, word in enumerate(words):
        stem = PurePath(word.replace("\\", "/")).name.lower().removesuffix(".cmd")
        if stem == "grillspec" and words[index + 1 : index + 3] == ["gate", "pause"]:
            return True
    return False


def _without_patch(lines: list[str]) -> list[str]:
    """Drop the lines of a ``*** Begin Patch`` … ``*** End Patch`` block.

    Args:
        lines: list[str] - Physical lines.

    Returns:
        list[str] - The lines outside any patch block.

    """
    kept: list[str] = []
    inside = False
    for line in lines:
        if line.strip() == _PATCH_BEGIN:
            inside = True
        elif inside and line.strip() == _PATCH_END:
            inside = False
        elif not inside:
            kept.append(line)
    return kept


def _simple(
    scan: _Scan, words: list[str], targets: list[str], *, patched: bool
) -> None:
    """Scan one simple command: ``cd``, nested shells, the pause, writes.

    Args:
        scan: _Scan - Findings so far.
        words: list[str] - Unquoted words.
        targets: list[str] - Its redirection targets.
        patched: bool - The command carries a Codex patch.

    """
    for target in targets:
        if target.lower() not in _SINKS:
            scan.add(target)
    scan.pause = scan.pause or _pause(words)
    name, args = _command(words)
    if name == "cd":
        destination = next((arg for arg in args if not arg.startswith("-")), "~")
        scan.base = str(PurePath(scan.base) / destination) if scan.base else destination
    elif name in _SHELLS and any(flag in args for flag in ("-c", "-Command")):
        flag = "-c" if "-c" in args else "-Command"
        inner = args[args.index(flag) + 1 :]
        nested = _scan(" ".join(inner))
        for path in nested.paths:
            scan.add(path)
        scan.unknown = scan.unknown or nested.unknown
        scan.pause = scan.pause or nested.pause
    else:
        _writes(scan, name, args, patched=patched)


def _scan(command: str) -> _Scan:
    """Scan a command line, possibly several lines long.

    Args:
        command: str - The command.

    Returns:
        _Scan - Paths, unknown writers and pause attempts.

    """
    scan = _Scan()
    patch = patch_paths(command) if _PATCH_BEGIN in command else []
    for path in patch:
        scan.add(path)
    heredoc: str | None = None
    pending: str | None = None
    lines = _without_patch(command.splitlines())
    for number, line in enumerate(lines):
        if heredoc is not None:
            if line.strip() == heredoc:
                heredoc = None
            continue
        pending = line if pending is None else f"{pending}\n{line}"
        tokens = _lex(pending)
        if tokens is None and number < len(lines) - 1:
            continue  # a quote spans lines: read on
        segments, heredoc = _segments(tokens if tokens is not None else pending.split())
        pending = None
        for words, targets in segments:
            _simple(scan, words, targets, patched=bool(patch))
    return scan


def shell_targets(command: str) -> tuple[list[str], bool]:
    """Find the files a shell command obviously writes.

    Args:
        command: str - The command line, possibly several lines.

    Returns:
        tuple[list[str], bool] - Written paths (deduplicated, in order, without
            ``/dev/null`` and friends), and whether some writer's target is
            unknown (``git restore``, a bare ``apply_patch``).

    """
    scan = _scan(command)
    return list(dict.fromkeys(scan.paths)), scan.unknown


def pause_attempt(command: str) -> bool:
    """Tell whether a shell command runs ``grillspec gate pause``, however quoted.

    Args:
        command: str - The command line.

    Returns:
        bool - True when it does.

    """
    return _scan(command).pause
