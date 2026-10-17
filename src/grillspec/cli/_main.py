"""Argument parsing and command dispatch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

from grillspec import __version__
from grillspec.config import ConfigError, load_config
from grillspec.state import UnknownChangeError, compute_status, set_active

if TYPE_CHECKING:
    from collections.abc import Sequence


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
    return parser


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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Sequence[str] | None - Arguments without the program name; the process
            arguments when None.

    Returns:
        int - The process exit code.

    """
    args = _build_parser().parse_args(argv)
    command = cast("str", args.command)
    try:
        if command == "status":
            return _status(as_json=cast("bool", args.json))
        if command == "use":
            return _use(cast("str", args.change_id))
    except ConfigError as error:
        _ = sys.stderr.write(f"grillspec: {error}\n")
        return 1
    _ = sys.stdout.write(f"{__version__}\n")
    return 0
