"""Argument parsing and command dispatch."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

from grillspec import __version__
from grillspec.blocks import BlockError
from grillspec.config import Backend, ConfigError, Depth, External, load_config
from grillspec.council import (
    CouncilError,
    build_argv,
    member_spec,
    parse_payload,
    render_prompt,
    resolve_cli,
    resolve_members,
    run_members,
)
from grillspec.detect import brownfield_signals, cli_report, recommend_backend
from grillspec.hooks import Harness, render_session_start, session_context
from grillspec.init import init_project
from grillspec.install import InstallConflictError, Scope, install, uninstall
from grillspec.paths import project_root, write_atomic
from grillspec.specs import Report, openspec_advice, validate_change
from grillspec.state import (
    ChangeError,
    Stage,
    UnknownChangeError,
    active_change_id,
    approve,
    compute_status,
    create_change,
    list_changes,
    set_active,
)

if TYPE_CHECKING:
    import io
    from collections.abc import Callable, Sequence


def _add_council(council: argparse.ArgumentParser) -> None:
    """Add ``council ask`` to the ``council`` parser.

    Args:
        council: argparse.ArgumentParser - The ``council`` sub-parser.

    """
    council_commands = council.add_subparsers(dest="council_command", required=True)
    ask = council_commands.add_parser(
        "ask", help="ask one decision (JSON payload on stdin)"
    )
    _ = ask.add_argument("--members", help="comma-separated cli:<vendor>[@<model>]")
    _ = ask.add_argument("--payload", help="read the payload from this UTF-8 file")
    _ = ask.add_argument(
        "--out", help="also write the result (or the error) to this file, atomically"
    )
    _ = ask.add_argument("--timeout", type=int, help="seconds per member (1-600)")
    _ = ask.add_argument("--dry-run", action="store_true", help="only print calls")


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
    new = commands.add_parser("new", help="start a change and its decision log")
    _ = new.add_argument("slug", help="lowercase kebab-case name")
    _ = new.add_argument(
        "--switch", action="store_true", help="leave the active change"
    )
    _ = new.add_argument("--depth", choices=[str(d) for d in Depth])
    _ = new.add_argument("--council", action="store_true", help="grill with a council")
    _add_council(commands.add_parser("council", help="ask external agent CLIs"))
    check = commands.add_parser("validate", help="check a change's spec")
    _ = check.add_argument("change_id", nargs="?", help="change id (default: active)")
    _ = check.add_argument("--json", action="store_true", help="print JSON")
    approve_cmd = commands.add_parser("approve", help="record an approval")
    _ = approve_cmd.add_argument("stage", choices=[str(s) for s in Stage])
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


def _new(slug: str, *, switch: bool, depth: str | None, council: bool) -> int:
    """Create a change and print its id and decision-log path.

    Args:
        slug: str - Change name.
        switch: bool - Allow leaving an unfinished active change.
        depth: str | None - Grilling depth, or None for the configured default.
        council: bool - Whether the grill consults a council.

    Returns:
        int - Exit code.

    """
    root = project_root(Path.cwd())
    change = create_change(
        root,
        load_config(root).config,
        slug,
        today=dt.datetime.now().astimezone().date(),
        switch=switch,
        depth=Depth(depth) if depth else None,
        council=council,
    )
    log = change.log_path.relative_to(root).as_posix() if change.log_path else "-"
    return _print(f"created {change.id}; decision log: {log}")


def _plan_refusal(root: Path, backend: Backend) -> str | None:
    """Tell why the plan of the active change cannot be approved yet.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.

    Returns:
        str | None - The reason, or None when the approved spec is current.

    """
    change_id, _ = active_change_id(root)
    change = next((c for c in list_changes(root, backend) if c.id == change_id), None)
    if change is None:
        return None
    if change.spec_approved is None:
        return "approve the spec first: grillspec approve spec"
    if change.spec_stale:
        return "spec changed since approval: review it, then grillspec approve spec"
    return None


def _approve(stage: str) -> int:
    """Record today's approval of a stage for the active change.

    Args:
        stage: str - ``grill``, ``spec`` or ``plan``.

    Returns:
        int - Exit code: 1 when grillspec is not set up or no change is active.

    """
    root = project_root(Path.cwd())
    backend = load_config(root).config.backend
    if backend is None:
        _ = sys.stderr.write("grillspec is not set up here; run grillspec init\n")
        return 1
    if Stage(stage) is Stage.PLAN:
        refusal = _plan_refusal(root, backend)
        if refusal is not None:
            _ = sys.stderr.write(f"grillspec: {refusal}\n")
            return 1
    if Stage(stage) is Stage.SPEC:
        change_id, _ = active_change_id(root)
        if change_id is not None:
            report = validate_change(root, backend, change_id)
            if report.errors:
                for finding in report.errors:
                    _ = sys.stderr.write(finding.text() + "\n")
                _ = sys.stderr.write("grillspec: fix these, then approve again\n")
                return 1
    sidecar = approve(
        root, backend, Stage(stage), today=dt.datetime.now().astimezone().date()
    )
    return _print(f"approved {stage} for {sidecar.stem}")


MAX_TIMEOUT = 600


def _council_ask(
    members: str | None,
    timeout: int | None,
    payload_path: str | None,
    out: str | None,
    *,
    dry_run: bool,
) -> int:
    """Run ``council ask``; with ``--out``, also leave the result or error there.

    The file appears only when the call is over, so a background caller can wait
    for it.

    Args:
        members: str | None - ``--members``, or None for the configured ones.
        timeout: int | None - ``--timeout``, or None for ``council.timeout``.
        payload_path: str | None - ``--payload`` file; None reads stdin.
        out: str | None - ``--out`` file, or None.
        dry_run: bool - Print each call instead of making it.

    Returns:
        int - Exit code, as ``_council_ask_run``.

    Raises:
        CouncilError: Re-raised after the error is written to ``out``.
        ConfigError: Re-raised after the error is written to ``out``.

    """
    try:
        code, result = _council_ask_run(members, timeout, payload_path, dry_run=dry_run)
    except (CouncilError, ConfigError) as error:
        if out is not None:
            write_atomic(
                Path(out), json.dumps({"version": 1, "error": str(error)}) + "\n"
            )
        raise
    text = json.dumps(result) + "\n"
    if out is not None:
        write_atomic(Path(out), text)
    if code == 0:
        _ = sys.stdout.write(text)
    else:
        _ = sys.stderr.write(f"grillspec: {result['error']}\n")
    return code


def _council_ask_run(
    members: str | None, timeout: int | None, payload_path: str | None, *, dry_run: bool
) -> tuple[int, dict[str, object]]:
    """Ask external council members about one decision.

    Args:
        members: str | None - ``--members``, or None for the configured ones.
        payload_path: str | None - ``--payload`` file; None reads stdin.
        timeout: int | None - ``--timeout``, or None for ``council.timeout``.
        dry_run: bool - Print each call instead of making it.

    Returns:
        tuple[int, dict[str, object]] - Exit code and the JSON result: 1 with an
            ``error`` when external members are disabled; 0 otherwise, even when
            every member failed.

    Raises:
        CouncilError: If the members, the timeout or the payload are invalid.

    """
    root = project_root(Path.cwd())
    config = load_config(root).config
    if config.council_external is External.NEVER:
        disabled = 'external council members are disabled (council.external = "never")'
        return 1, {"version": 1, "error": disabled}
    chosen = resolve_members(members, config.council_members)
    seconds = config.council_timeout if timeout is None else timeout
    if not 1 <= seconds <= MAX_TIMEOUT:
        msg = f"--timeout must be from 1 to 600 seconds, not {seconds}"
        raise CouncilError(msg)
    argvs = [build_argv(m, resolve_cli(m.name) or m.name) for m in chosen]
    prompt = render_prompt(parse_payload(_read_payload(payload_path)))
    share = root if config.council_share_project else None
    payload: dict[str, object]
    if dry_run:
        calls = [
            {
                "name": member_spec(member),
                "argv": argv,
                "cwd": str(share) if share else "<new empty temp dir>",
                "prompt": prompt,
            }
            for member, argv in zip(chosen, argvs, strict=True)
        ]
        payload = {"version": 1, "dry_run": True, "members": calls}
    else:
        results = run_members(chosen, prompt, timeout=seconds, project_root=share)
        payload = {"version": 1, "members": [r.to_json() for r in results]}
    return 0, payload


def _read_payload(path: str | None) -> str:
    """Read the payload as UTF-8 from a file or stdin, whatever the code page.

    Args:
        path: str | None - Payload file; None reads stdin.

    Returns:
        str - The text.

    Raises:
        CouncilError: If the file cannot be read or the bytes are not UTF-8.

    """
    if path is None:
        buffer = cast("io.BufferedIOBase | None", getattr(sys.stdin, "buffer", None))
        data = buffer.read() if buffer is not None else sys.stdin.read().encode()
    else:
        try:
            data = Path(path).read_bytes()
        except OSError as error:
            msg = f"council payload {path}: {error.strerror or error}"
            raise CouncilError(msg) from None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        msg = f"council payload is not UTF-8: {error}"
        raise CouncilError(msg) from None


def _validate(change_id: str | None, *, as_json: bool) -> int:
    """Check a change's spec and print what was found.

    Args:
        change_id: str | None - Change id; None for the active change.
        as_json: bool - Print JSON instead of one line per finding.

    Returns:
        int - Exit code: 1 when there are errors or grillspec is not set up.

    Raises:
        ChangeError: If no change is given and none is active, or the id is unknown.

    """
    root = project_root(Path.cwd())
    backend = load_config(root).config.backend
    if backend is None:
        _ = sys.stderr.write("grillspec is not set up here; run grillspec init\n")
        return 1
    if change_id is None:
        change_id, _ = active_change_id(root)
    if change_id is None:
        msg = "no active change; run grillspec new or grillspec use"
        raise ChangeError(msg)
    report = validate_change(root, backend, change_id)
    if backend is Backend.OPENSPEC:
        advice = openspec_advice(root, change_id)
        report = Report(report.change, report.errors, (*report.warnings, *advice))
    if as_json:
        _ = sys.stdout.write(json.dumps(report.to_json()) + "\n")
    else:
        for finding in (*report.errors, *report.warnings):
            _ = sys.stdout.write(finding.text() + "\n")
        counts = f"{len(report.errors)} errors, {len(report.warnings)} warnings"
        _ = sys.stdout.write(counts + "\n")
    return 1 if report.errors else 0


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
        Harness(harness),
        Scope(scope),
        root=project_root(Path.cwd()),
        copy=copy,
        dry_run=dry_run,
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
    touched = uninstall(Harness(harness), Scope(scope), root=project_root(Path.cwd()))
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
    clis = cli_report()
    if as_json:
        payload = {
            "version": 1,
            "signals": {
                "has_source": signals.has_source,
                "has_openspec": signals.has_openspec,
                "commit_count": signals.commit_count,
            },
            "recommended_backend": str(recommended),
            "clis": {
                name: {
                    "installed": cli.installed,
                    "authenticated": cli.authenticated,
                    "experimental": cli.experimental,
                }
                for name, cli in clis.items()
            },
        }
        _ = sys.stdout.write(json.dumps(payload) + "\n")
        return 0
    auth = {True: "logged in", False: "not logged in", None: "auth unknown"}
    found = (
        ", ".join(
            f"{name} ({auth[cli.authenticated]})"
            for name, cli in clis.items()
            if cli.installed
        )
        or "none"
    )
    lines = (
        f"source code: {signals.has_source}",
        f"openspec/: {signals.has_openspec}",
        f"commits: {signals.commit_count}",
        f"recommended backend: {recommended}",
        f"agent CLIs: {found}",
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
    payload = render_session_start(
        Harness(harness), session_context(project_root(Path.cwd()))
    )
    _ = sys.stdout.write(payload + "\n")
    return 0


def _status(*, as_json: bool) -> int:
    """Print the status of the current working tree.

    Args:
        as_json: bool - Print JSON instead of the one-line form.

    Returns:
        int - Exit code.

    """
    root = project_root(Path.cwd())
    loaded = load_config(root)
    status = compute_status(root, loaded.config)
    warnings = [*loaded.warnings, *status.warnings]
    if as_json:
        payload = {
            "version": 1,
            "phase": str(status.phase),
            "change": status.change_id,
            "next": status.next_step,
            "open_questions": status.open_questions,
            "log": status.log.as_posix() if status.log else None,
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
    root = project_root(Path.cwd())
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
        "validate": lambda: _validate(
            cast("str | None", args.change_id), as_json=cast("bool", args.json)
        ),
        "approve": lambda: _approve(cast("str", args.stage)),
        "council": lambda: _council_ask(
            cast("str | None", args.members),
            cast("int | None", args.timeout),
            cast("str | None", args.payload),
            cast("str | None", args.out),
            dry_run=cast("bool", args.dry_run),
        ),
        "new": lambda: _new(
            cast("str", args.slug),
            switch=cast("bool", args.switch),
            depth=cast("str | None", args.depth),
            council=cast("bool", args.council),
        ),
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
    except (ConfigError, InstallConflictError, ChangeError, CouncilError) as error:
        _ = sys.stderr.write(f"grillspec: {error}\n")
        return 1
