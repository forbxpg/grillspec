"""Fake agent CLIs on PATH that record how they were called, on every OS."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

_SCRIPT = r"""
import json, os, subprocess, sys, time
cfg = json.loads({config!r})
argv = sys.argv[1:]
probe = argv in ([["auth", "status"], ["login", "status"], ["status", "--format", "json"]])
stdin = sys.stdin.buffer.read().decode("utf-8", "replace") if sys.stdin else ""
child = None
if cfg["spawn_child"] and not probe:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"]).pid
if cfg["record"]:
    with open(cfg["record"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"argv": argv, "stdin": stdin, "cwd": os.getcwd(),
                             "child_pid": child, "probe": probe, "pid": os.getpid(),
                             "files": sorted(os.listdir("."))}}) + "\n")
if probe:
    sys.stdout.buffer.write(cfg["probe_stdout"].encode("utf-8"))
    sys.exit(cfg["probe_exit"])
time.sleep(cfg["sleep"])
sys.stdout.buffer.write(cfg["stdout"].encode("utf-8", "surrogateescape"))
sys.stderr.write(cfg["stderr"])
sys.exit(cfg["exit_code"])
"""


def make_fake(  # ruff: ignore[too-many-arguments] - every knob is keyword-only
    bin_dir: Path,
    name: str,
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    sleep: float = 0,
    probe_stdout: str = "",
    probe_exit: int = 0,
    record: Path | None = None,
    spawn_child: bool = False,
) -> Path:
    """Write a fake CLI that answers probes and prompts as configured.

    A probe call (its argv equals a vendor's auth probe) answers with
    ``probe_stdout``/``probe_exit`` at once; any other call answers with
    ``stdout``/``stderr``/``exit_code`` after ``sleep`` seconds. Each call
    appends one JSON line ``{argv, stdin, cwd, child_pid, probe, pid, files}`` to ``record``.
    A lone surrogate in ``stdout`` (``"\\udcff"``) is written as that raw byte.

    Returns:
        Path - The shim on PATH (``name`` on POSIX, ``name.cmd`` on Windows).

    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    config = json.dumps({
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "sleep": sleep,
        "probe_stdout": probe_stdout,
        "probe_exit": probe_exit,
        "record": str(record) if record else None,
        "spawn_child": spawn_child,
    })
    script = bin_dir / f"_{name}_fake.py"
    _ = script.write_text(_SCRIPT.format(config=config), encoding="utf-8")
    if sys.platform == "win32":
        shim = bin_dir / f"{name}.cmd"
        _ = shim.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        shim = bin_dir / name
        _ = shim.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8"
        )
        shim.chmod(0o755)
    return shim


def records(path: Path) -> list[dict[str, object]]:
    """Read every call a fake recorded.

    Returns:
        list[dict[str, object]] - One entry per call, oldest first; empty when
            the fake was never called.

    """
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [cast("dict[str, object]", json.loads(line)) for line in lines]


def alive(pid: int) -> bool:
    """Tell whether a process still runs.

    Returns:
        bool - True while the process exists.

    """
    if sys.platform == "win32":
        done = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in done.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def gone(pid: int, within: float = 5.0) -> bool:
    """Wait for a process to disappear (zombies take a moment to be reaped).

    Returns:
        bool - True when the process is gone within the time.

    """
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        if not alive(pid):
            return True
        time.sleep(0.1)
    return not alive(pid)
