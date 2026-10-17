"""Argument parsing and command dispatch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

from grillspec import __version__
from grillspec.blocks import BlockError
from grillspec.config import Backend, ConfigError, load_config
from grillspec.detect import available_clis, brownfield_signals, recommend_backend
from grillspec.hooks import Harness, render_session_start, session_context
from grillspec.init import init_project
from grillspec.install import Scope, install, uninstall
from grillspec.state import UnknownChangeError, compute_status, set_active

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with one sub-parser per command.

    Returns:
        argparse.ArgumentParser - The configured parser.

    """
    parser = argparse.ArgumentParser(
        prog="grillspec",
        description="Spec-driven agentic development: grill, spec, plan, execute.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    _ = commands.add_parser("version", help="print the grillspec version")
    status = commands.add_parser("status", help="show the phase of this working tree")
    _ = status.add_argument("--json", action="store_true", help="print JSON")
    use = commands.add_parser("use", help="make a change the active one")
    _ = use.add_argument("change_id", help="id of an existing change")
    hook = commands.add_parser("hook", help="entry point for harness hooks")
    _ = hook.add_argument("event", choices=["session-start"])
    _ = hook.add_argument(
        "--harness",
        required=True,
        choices=[str(h) for h in Harness if h is not Harness.GIGACODE],
    )
    init = commands.add_parser("init", help="set grillspec up in this project")
    _ = init.add_argument("--backend", required=True, choices=[str(b) for b in Backend])
    _ = init.add_argument("--dry-run", action="store_true", help="only list changes")
    detect = commands.add_parser("detect", help="brownfield signals and agent CLIs")
    _ = detect.add_argument("--json", action="store_true", help="print JSON")
    harnesses = [str(h) for h in Harness]
    scopes = [str(s) for s in Scope]
    inst = commands.add_parser("install", help="install skills into a harness")
    _ = inst.add_argument("--harness", required=True, choices=harnesses)
    _ = inst.add_argument("--scope", choices=scopes, default=str(Scope.PROJECT))
    _ = inst.add_argument("--copy", action="store_true", help="copy even with plugins")
    _ = inst.add_argument("--dry-run", action="store_true", help="only list writes")
    uninst = commands.add_parser("uninstall", help="remove what install wrote")
    _ = uninst.add_argument("--harness", required=True, choices=harnesses)
    _ = uninst.add_argument("--scope", choices=scopes, default=str(Scope.PROJECT))
    return parser


def _install(harness: str, scope: str, *, copy: bool, dry_run: bool) -> int:
    """Install skills for a harness, or print its native install command.

    Args:
        harness: str - Harness name.
        scope: str - ``project`` or ``user``.
        copy: bool - Copy even when the harness has plugins.
        dry_run: bool - Only list planned writes.

    Returns:
        int - Exit code.

    """
    result = install(
        Harness(harness), Scope(scope), root=Path.cwd(), copy=copy, dry_run=dry_run
    )
    if result.native_command is not None:
        return _print(f"{harness} has native plugins; run: {result.native_command}")
    verb = "would write" if dry_run else "wrote"
    for path in result.planned:
        _ = sys.stdout.write(f"{verb}: {path}\n")
    return 0


def _uninstall(harness: str, scope: str) -> int:
    """Remove what an install recorded.

    Args:
        harness: str - Harness name.
        scope: str - ``project`` or ``user``.

    Returns:
        int - Exit code.

    """
    touched = uninstall(Harness(harness), Scope(scope), root=Path.cwd())
    if not touched:
        return _print(f"nothing recorded for {harness} ({scope})")
    for path in touched:
        _ = sys.stdout.write(f"removed: {path}\n")
    return 0


def _init(backend: str, *, dry_run: bool) -> int:
    """Set grillspec up in the current directory and list changed files.

    Args:
        backend: str - Spec backend.
        dry_run: bool - Only list what would change.

    Returns:
        int - Exit code: 1 when a managed block is broken.

    """
    root = Path.cwd()
    try:
        changed = init_project(root, Backend(backend), dry_run=dry_run)
    except BlockError as error:
        _ = sys.stderr.write(f"grillspec: {error}\n")
        return 1
    verb = "would change" if dry_run else "changed"
    for path in changed:
        _ = sys.stdout.write(f"{verb}: {path.relative_to(root).as_posix()}\n")
    if not changed:
        _ = sys.stdout.write("already set up\n")
    return 0


def _detect(*, as_json: bool) -> int:
    """Report brownfield signals, the recommended backend and agent CLIs.

    Args:
        as_json: bool - Print JSON instead of text.

    Returns:
        int - Exit code.

    """
    signals = brownfield_signals(Path.cwd())
    recommended = recommend_backend(signals)
    clis = available_clis()
    if as_json:
        payload = {
            "version": 1,
            "signals": {
                "has_source": signals.has_source,
                "has_openspec": signals.has_openspec,
                "commit_count": signals.commit_count,
            },
            "recommended_backend": str(recommended),
            "clis": clis,
        }
        _ = sys.stdout.write(json.dumps(payload) + "\n")
        return 0
    found = ", ".join(name for name, present in clis.items() if present) or "none"
    lines = (
        f"source code: {signals.has_source}",
        f"openspec/: {signals.has_openspec}",
        f"commits: {signals.commit_count}",
        f"recommended backend: {recommended}",
        f"agent CLIs on PATH: {found}",
    )
    _ = sys.stdout.write("\n".join(lines) + "\n")
    return 0


def _hook(harness: str) -> int:
    """Print the session-start payload for a harness; never fails.

    Args:
        harness: str - Harness name.

    Returns:
        int - Always 0: hooks are fail-open.

    """
    payload = render_session_start(Harness(harness), session_context(Path.cwd()))
    _ = sys.stdout.write(payload + "\n")
    return 0


def _status(*, as_json: bool) -> int:
    """Print the status of the current working tree.

    Args:
        as_json: bool - Print JSON instead of the one-line form.

    Returns:
        int - Exit code.

    """
    root = Path.cwd()
    loaded = load_config(root)
    status = compute_status(root, loaded.config)
    warnings = [*loaded.warnings, *status.warnings]
    if as_json:
        payload = {
            "version": 1,
            "phase": str(status.phase),
            "change": status.change_id,
            "next": status.next_step,
            "warnings": warnings,
        }
        _ = sys.stdout.write(json.dumps(payload) + "\n")
    else:
        _ = sys.stdout.write(status.line() + "\n")
        for warning in warnings:
            _ = sys.stdout.write(f"WARNING: {warning}\n")
    return 0


def _use(change_id: str) -> int:
    """Make a change active in the current working tree.

    Args:
        change_id: str - Id of an existing change.

    Returns:
        int - Exit code: 1 when the change is unknown or grillspec is not set up.

    """
    root = Path.cwd()
    backend = load_config(root).config.backend
    if backend is None:
        _ = sys.stderr.write("grillspec is not set up here; run grillspec init\n")
        return 1
    try:
        set_active(root, change_id, backend)
    except UnknownChangeError as error:
        _ = sys.stderr.write(f"{error}\n")
        return 1
    return 0


def _print(text: str) -> int:
    """Print one line.

    Args:
        text: str - Line to print.

    Returns:
        int - Exit code 0.

    """
    _ = sys.stdout.write(f"{text}\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Sequence[str] | None - Arguments without the program name; the process
            arguments when None.

    Returns:
        int - The process exit code.

    """
    args = _build_parser().parse_args(argv)
    handlers: dict[str, Callable[[], int]] = {
        "version": lambda: _print(__version__),
        "status": lambda: _status(as_json=cast("bool", args.json)),
        "use": lambda: _use(cast("str", args.change_id)),
        "hook": lambda: _hook(cast("str", args.harness)),
        "init": lambda: _init(
            cast("str", args.backend), dry_run=cast("bool", args.dry_run)
        ),
        "detect": lambda: _detect(as_json=cast("bool", args.json)),
        "install": lambda: _install(
            cast("str", args.harness),
            cast("str", args.scope),
            copy=cast("bool", args.copy),
            dry_run=cast("bool", args.dry_run),
        ),
        "uninstall": lambda: _uninstall(
            cast("str", args.harness), cast("str", args.scope)
        ),
    }
    try:
        return handlers[cast("str", args.command)]()
    except ConfigError as error:
        _ = sys.stderr.write(f"grillspec: {error}\n")
        return 1
