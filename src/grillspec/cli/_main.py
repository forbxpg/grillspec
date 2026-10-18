"""Argument parsing and command dispatch."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

from grillspec import __version__
from grillspec.archive import ArchiveError, archive_change
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
from grillspec.execute import (
    ExecError,
    ExecTarget,
    finish_task,
    review_package,
    start_task,
    workspace,
)
from grillspec.gates import GATED, pre_tool
from grillspec.hooks import Harness, render_session_start, session_context
from grillspec.init import init_project
from grillspec.install import InstallConflictError, Scope, install, uninstall
from grillspec.memory import (
    CATEGORIES,
    MAX_ENTRIES,
    Entry,
    MemoryBlockError,
    add_entry,
    read_entries,
    retire_entry,
)
from grillspec.paths import data_root, project_root, write_atomic
from grillspec.specs import (
    Finding,
    Report,
    openspec_advice,
    plan_report,
    validate_change,
)
from grillspec.state import (
    ChangeError,
    Stage,
    UnknownChangeError,
    active_change_id,
    approve,
    compute_status,
    create_change,
    list_changes,
    pause_gates,
    plan_path,
    resume_gates,
    set_active,
)
from grillspec.tokens import BYTES_PER_TOKEN, ROUTER, measure, render_markdown

if TYPE_CHECKING:
    import io
    from collections.abc import Callable, Sequence


def _add_exec(execute: argparse.ArgumentParser) -> None:
    """Add ``exec workspace|start|done|review-package`` to the ``exec`` parser.

    Args:
        execute: argparse.ArgumentParser - The ``exec`` sub-parser.

    """
    actions = execute.add_subparsers(dest="exec_command", required=True)
    _ = actions.add_parser("workspace", help="print the execution workspace")
    start = actions.add_parser("start", help="write a task's brief; print BASE")
    _ = start.add_argument("task", help="task number, N.M")
    done = actions.add_parser("done", help="run a task's tests; tick it on success")
    _ = done.add_argument("task", help="task number, N.M")
    _ = done.add_argument("base", help="BASE printed by start")
    _ = done.add_argument(
        "test_command", nargs=argparse.REMAINDER, help="-- <test command>"
    )
    review = actions.add_parser("review-package", help="write a review diff")
    _ = review.add_argument("base")
    _ = review.add_argument("head", nargs="?", default="HEAD")


def _add_memory(memory: argparse.ArgumentParser) -> None:
    """Add ``memory list|add|retire`` to the ``memory`` parser.

    Args:
        memory: argparse.ArgumentParser - The ``memory`` sub-parser.

    """
    actions = memory.add_subparsers(dest="memory_command", required=True)
    listing = actions.add_parser("list", help="show the remembered facts")
    _ = listing.add_argument("--json", action="store_true", help="print JSON")
    add = actions.add_parser("add", help="remember one fact")
    _ = add.add_argument(
        "--category", required=True, metavar="{" + ",".join(CATEGORIES) + "}"
    )
    _ = add.add_argument("--change", required=True, help="id of the source change")
    _ = add.add_argument("text", help="the fact, one line (put -- before it)")
    retire = actions.add_parser("retire", help="forget fact <n> (as listed)")
    _ = retire.add_argument("number", type=int)


def _add_tokens(tokens: argparse.ArgumentParser) -> None:
    """Add the ``tokens`` options.

    Args:
        tokens: argparse.ArgumentParser - The ``tokens`` sub-parser.

    """
    shape = tokens.add_mutually_exclusive_group()
    _ = shape.add_argument("--json", action="store_true", help="print JSON")
    _ = shape.add_argument(
        "--markdown", action="store_true", help="print the docs table"
    )
    _ = tokens.add_argument(
        "--project", action="store_true", help="include this project's memory block"
    )


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
    _ = hook.add_argument("event", choices=["session-start", "pre-tool"])
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
    _add_memory(commands.add_parser("memory", help="project memory in AGENTS.md"))
    _add_exec(commands.add_parser("exec", help="helpers that execute the plan"))
    _ = commands.add_parser("gate", help="pause or resume the phase gate").add_argument(
        "action", choices=["pause", "resume"]
    )
    _add_tokens(commands.add_parser("tokens", help="estimate grillspec's context cost"))
    _ = commands.add_parser(
        "archive", help="archive the done active change"
    ).add_argument("--dry-run", action="store_true", help="only list it")
    check = commands.add_parser("validate", help="check a change's spec")
    _ = check.add_argument("change_id", nargs="?", help="change id (default: active)")
    _ = check.add_argument("--json", action="store_true", help="print JSON")
    approve_cmd = commands.add_parser("approve", help="record an approval")
    _ = approve_cmd.add_argument("stage", choices=[str(s) for s in Stage])
    _ = approve_cmd.add_argument(
        "--executor", choices=["subagent", "inline"], help="plan: how to execute it"
    )
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
        str | None - The reason, or None when the approved spec is current, the
            plan exists and no task is ticked yet.

    """
    change_id, _ = active_change_id(root)
    change = next((c for c in list_changes(root, backend) if c.id == change_id), None)
    if change is None:
        return None
    if change.spec_approved is None:
        return "approve the spec first: grillspec approve spec"
    if change.spec_stale:
        return "spec changed since approval: review it, then grillspec approve spec"
    if change.plan_path is None:
        where = plan_path(root, backend, change.id).relative_to(root).as_posix()
        return f"no plan at {where}; write it first"
    # Re-approving an edited plan mid-execution keeps its ticks: the hash ignores
    # them. Only a first approval must start from an unticked plan.
    if change.plan_checked and change.plan_approved is None:
        return "uncheck the plan's tasks before approving it"
    return None


def _refuse(findings: Sequence[Finding]) -> int:
    """Print blocking findings and the one-line verdict.

    Args:
        findings: Sequence[Finding] - The errors.

    Returns:
        int - Exit code 1.

    """
    for finding in findings:
        _ = sys.stderr.write(finding.text() + "\n")
    _ = sys.stderr.write("grillspec: fix these, then approve again\n")
    return 1


def _approve(stage: str, executor: str | None = None) -> int:
    """Record today's approval of a stage for the active change.

    Args:
        stage: str - ``grill``, ``spec`` or ``plan``.
        executor: str | None - For the plan: ``subagent`` or ``inline``.

    Returns:
        int - Exit code: 1 when grillspec is not set up, no change is active, or
            the spec or plan is not ready to approve.

    """
    root = project_root(Path.cwd())
    backend = load_config(root).config.backend
    if backend is None:
        _ = sys.stderr.write("grillspec is not set up here; run grillspec init\n")
        return 1
    change_id, _ = active_change_id(root)
    if Stage(stage) is Stage.PLAN:
        refusal = _plan_refusal(root, backend)
        if refusal is not None:
            _ = sys.stderr.write(f"grillspec: {refusal}\n")
            return 1
        if change_id is not None:
            errors = [
                f
                for f in plan_report(root, backend, change_id)
                if f.severity == "error"
            ]
            if errors:
                return _refuse(errors)
    if Stage(stage) is Stage.SPEC and change_id is not None:
        report = validate_change(root, backend, change_id, include_plan=False)
        if report.errors:
            return _refuse(report.errors)
    sidecar = approve(
        root,
        backend,
        Stage(stage),
        today=dt.datetime.now().astimezone().date(),
        executor=executor if Stage(stage) is Stage.PLAN else None,
    )
    resume_gates(root)  # a pause lasts one phase; approval moves the phase on
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


def _exec_target(root: Path) -> ExecTarget | str:
    """Resolve the change ``grillspec exec`` acts on.

    Args:
        root: Path - Project root.

    Returns:
        ExecTarget | str - The target, or the one-line reason there is none.

    """
    backend = load_config(root).config.backend
    if backend is None or not (root / ".grillspec" / "config.toml").is_file():
        return "grillspec is not set up here; run grillspec init"
    change_id, _ = active_change_id(root)
    if change_id is None:
        return "no active change; run grillspec use <id>"
    return ExecTarget(root, plan_path(root, backend, change_id), change_id)


def _exec_run(target: ExecTarget, args: argparse.Namespace) -> int:
    """Run one execution helper.

    Args:
        target: ExecTarget - The change being executed.
        args: argparse.Namespace - Parsed ``exec`` arguments.

    Returns:
        int - Exit code.

    Raises:
        ExecError: If the helper cannot do what was asked.

    """
    action = cast("str", args.exec_command)
    if action == "workspace":
        return _print(workspace(target.root, target.change_id).resolve().as_posix())
    if action == "review-package":
        base, head = cast("str", args.base), cast("str", args.head)
        path = review_package(target.root, target.change_id, base, head)
        return _print(path.resolve().as_posix())
    if not target.plan.is_file():
        where = target.plan.relative_to(target.root).as_posix()
        msg = f"no plan at {where}"
        raise ExecError(msg)
    if action == "start":
        brief, base = start_task(target, cast("str", args.task))
        _ = sys.stdout.write(f"brief: {brief.resolve().as_posix()}\n")
        return _print(f"base: {base}")
    command = list(cast("list[str]", args.test_command))
    command = command[1:] if command[:1] == ["--"] else command
    task, base = cast("str", args.task), cast("str", args.base)
    code, tail = finish_task(target, task, base, command)
    if tail:
        _ = sys.stdout.write(tail + "\n")
    return code


def _exec(args: argparse.Namespace) -> int:
    """Run one execution helper on the active change's plan.

    Args:
        args: argparse.Namespace - Parsed ``exec`` arguments.

    Returns:
        int - Exit code: 1 for setup problems, 3 for a bad review range, the
            test command's own code for ``done``.

    """
    target = _exec_target(project_root(Path.cwd()))
    if isinstance(target, str):
        _ = sys.stderr.write(
            f"grillspec: {target}\n" if "not set up" not in target else f"{target}\n"
        )
        return 1
    try:
        return _exec_run(target, args)
    except ExecError as error:
        _ = sys.stderr.write(f"grillspec: {error}\n")
        return error.code


def _archive(*, dry_run: bool) -> int:
    """Archive the active change and print what changed.

    Args:
        dry_run: bool - Only list the operations.

    Returns:
        int - Exit code: 1 when grillspec is not set up or the change cannot be
            archived.

    """
    root = project_root(Path.cwd())
    config = load_config(root).config
    if config.backend is None:
        _ = sys.stderr.write("grillspec is not set up here; run grillspec init\n")
        return 1
    today = dt.datetime.now().astimezone().date()
    try:
        ops = archive_change(root, config, today=today, dry_run=dry_run)
    except ArchiveError as error:
        _ = sys.stderr.write(f"grillspec: {error}\n")
        return 1
    for line in ops:
        _ = sys.stdout.write(f"{'would ' if dry_run else ''}{line}\n")
    return 0


def _memory(args: argparse.Namespace) -> int:
    """List, add or retire remembered facts in the project's AGENTS.md.

    Args:
        args: argparse.Namespace - Parsed ``memory`` arguments.

    A broken block or a refused change raises ``MemoryBlockError``, which
    ``main`` reports as one line.

    Returns:
        int - Exit code: 1 when grillspec is not set up here.

    """
    root = project_root(Path.cwd())
    # Only the project's own config counts: a backend in the user config must not
    # make every directory look set up.
    if not (root / ".grillspec" / "config.toml").is_file():
        _ = sys.stderr.write("grillspec is not set up here; run grillspec init\n")
        return 1
    # Write through a symlink (AGENTS.md -> CLAUDE.md is a common setup).
    agents = (root / "AGENTS.md").resolve()
    text = ""
    if agents.is_file():
        with agents.open(encoding="utf-8", newline="") as handle:
            text = handle.read()
    action = cast("str", args.memory_command)
    if action == "list":
        entries = read_entries(text)
        if cast("bool", args.json):
            listed = [
                {"n": n, "category": e.category, "text": e.text, "change": e.change}
                for n, e in enumerate(entries, 1)
            ]
            data = {"version": 1, "cap": MAX_ENTRIES, "entries": listed}
            return _print(json.dumps(data))
        for n, entry in enumerate(entries, 1):
            _ = sys.stdout.write(f"{n}. {entry.line().removeprefix('- ')}\n")
        return _print(f"{len(entries)}/{MAX_ENTRIES} entries")
    if action == "add":
        entry = Entry(
            cast("str", args.category), cast("str", args.text), cast("str", args.change)
        )
        updated = add_entry(text, entry)
        write_atomic(agents, updated)
        return _print(f"added {len(read_entries(updated))}/{MAX_ENTRIES}")
    number = cast("int", args.number)
    write_atomic(agents, retire_entry(text, number))
    return _print(f"retired {number}")


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


def _hook(event: str, harness: str) -> int:
    """Answer a harness hook; never fails.

    Args:
        event: str - ``session-start`` or ``pre-tool`` (reads the payload on stdin).
        harness: str - Harness name.

    Returns:
        int - Always 0: hooks are fail-open.

    """
    if event == "pre-tool":
        try:
            stdin = sys.stdin.buffer.read()
        except (OSError, ValueError):
            stdin = b""
        answer = pre_tool(Harness(harness), stdin, os.environ)
        if answer:
            _ = sys.stdout.write(answer + "\n")
        return 0
    payload = render_session_start(
        Harness(harness), session_context(project_root(Path.cwd()))
    )
    _ = sys.stdout.write(payload + "\n")
    return 0


def _tokens(*, as_json: bool, markdown: bool, project: bool) -> int:
    """Print grillspec's estimated context costs.

    Args:
        as_json: bool - Print JSON.
        markdown: bool - Print the table the docs embed.
        project: bool - Include the current project's memory block.

    Returns:
        int - Exit code 0.

    """
    try:
        costs = measure(data_root(), project_root(Path.cwd()) if project else None)
    except (BlockError, UnicodeDecodeError) as error:
        _ = sys.stderr.write(f"grillspec: AGENTS.md: {error}\n")
        return 1
    if not costs.skills:
        _ = sys.stderr.write("grillspec: no skills found next to the CLI\n")
        return 1
    if markdown:
        return _print(render_markdown(costs))
    if as_json:
        payload = {
            "version": 1,
            "bytes_per_token": BYTES_PER_TOKEN,
            "router": costs.router,
            "catalogue": costs.catalogue,
            "memory": costs.memory,
            "always_on": costs.always_on,
            "skills": [
                {"name": s.name, "body": s.body, "references": s.references}
                for s in costs.skills
            ],
        }
        return _print(json.dumps(payload, indent=2))
    lines = [
        f"always-on per session: ≈{costs.always_on:,} tokens",
        f"  router and status line  ≈{costs.router:,}",
        f"  skill catalogue         ≈{costs.catalogue:,}",
    ]
    if costs.memory is not None:
        lines.append(f"  memory block            ≈{costs.memory:,}")
    elif project:
        lines.append("  memory block            none")
    lines.append("when a skill is used:")
    width = max(len(s.name) for s in costs.skills)
    for skill in costs.skills:
        extra = f" (+≈{skill.references:,} references)" if skill.references else ""
        if skill.name == ROUTER:
            extra = f"{extra} (counted in the router above)"
        lines.append(f"  {skill.name:<{width}}  ≈{skill.body:,}{extra}")
    lines.append(f"estimates: UTF-8 bytes / {BYTES_PER_TOKEN}")
    return _print("\n".join(lines))


def _gate(action: str) -> int:
    """Pause or resume the phase gate for the active change.

    Args:
        action: str - ``pause`` or ``resume``.

    Returns:
        int - Exit code: 1 when there is nothing to pause.

    """
    root = project_root(Path.cwd())
    if action == "resume":
        resume_gates(root)
        return _print("gates resumed")
    status = compute_status(root, load_config(root).config)
    if status.change_id is None or status.phase not in GATED:
        where = status.change_id or "no change"
        msg = f"nothing to pause: {where} is in the {status.phase} phase"
        _ = sys.stderr.write(f"grillspec: {msg}\n")
        return 1
    if not sys.stdin.isatty():
        _ = sys.stderr.write(
            "grillspec: run grillspec gate pause in your own terminal; it asks first\n"
        )
        return 1
    question = f"Pause the phase gate for {status.change_id} in {status.phase}? [y/N] "
    if input(question).strip().lower() not in {"y", "yes"}:
        _ = sys.stderr.write("grillspec: not paused\n")
        return 1
    pause_gates(root, status.change_id, str(status.phase))
    return _print(
        f"gates paused for {status.change_id} while it is in the {status.phase} phase"
    )


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
    for stream in (sys.stdout, sys.stderr):  # a legacy console must not crash on ≈ or →
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            _ = reconfigure(errors="replace")
    args = _build_parser().parse_args(argv)
    handlers: dict[str, Callable[[], int]] = {
        "version": lambda: _print(__version__),
        "status": lambda: _status(as_json=cast("bool", args.json)),
        "use": lambda: _use(cast("str", args.change_id)),
        "hook": lambda: _hook(cast("str", args.event), cast("str", args.harness)),
        "gate": lambda: _gate(cast("str", args.action)),
        "tokens": lambda: _tokens(
            as_json=cast("bool", args.json),
            markdown=cast("bool", args.markdown),
            project=cast("bool", args.project),
        ),
        "init": lambda: _init(
            cast("str", args.backend), dry_run=cast("bool", args.dry_run)
        ),
        "detect": lambda: _detect(as_json=cast("bool", args.json)),
        "validate": lambda: _validate(
            cast("str | None", args.change_id), as_json=cast("bool", args.json)
        ),
        "approve": lambda: _approve(
            cast("str", args.stage), cast("str | None", args.executor)
        ),
        "memory": lambda: _memory(args),
        "exec": lambda: _exec(args),
        "archive": lambda: _archive(dry_run=cast("bool", args.dry_run)),
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
    except (
        ConfigError,
        InstallConflictError,
        ChangeError,
        CouncilError,
        MemoryBlockError,
    ) as error:
        _ = sys.stderr.write(f"grillspec: {error}\n")
        return 1
