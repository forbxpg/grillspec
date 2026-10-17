"""Run a child process and, at the timeout, kill it together with its children."""

from __future__ import annotations

import atexit
import contextlib
import os
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, cast

if TYPE_CHECKING:
    import io
    from collections.abc import Callable, Generator, Sequence
    from types import FrameType

# After the main process exits, how long its leftover children may hold the pipes.
LINGER_SECONDS = 2.0
# After killing a tree, how long to wait for its pipes to close.
_DRAIN_SECONDS = 5.0
# The same after the main process already exited and only leftovers hold the
# pipes: on POSIX the group kill closes them at once; on Windows leftovers of an
# exited parent are out of reach, so waiting longer gains nothing.
_LEFTOVER_DRAIN_SECONDS = 1.0

_LIVE: set[subprocess.Popen[bytes]] = set()
_LIVE_LOCK = threading.Lock()


@dataclass(frozen=True)
class Finished:
    """What a child process left behind.

    Attributes:
        returncode: int | None - Exit code; None when it timed out.
        stdout: bytes - Everything it printed.
        stderr: bytes - Everything it printed to stderr.

    """

    returncode: int | None
    stdout: bytes
    stderr: bytes


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    """Kill a process and every process it started.

    Args:
        process: subprocess.Popen[bytes] - A process started in its own group.

    """
    if sys.platform == "win32":
        taskkill = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
        # A fixed argv without a shell; the only variable is our child's pid.
        # nosemgrep
        _ = subprocess.run(
            [
                str(taskkill / "System32" / "taskkill.exe"),
                "/F",
                "/T",
                "/PID",
                str(process.pid),
            ],
            capture_output=True,
            check=False,
        )
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
    with contextlib.suppress(OSError):
        process.kill()


def kill_all() -> None:
    """Kill every process tree ``run_tree`` still has running."""
    with _LIVE_LOCK:
        live = list(_LIVE)
    for process in live:
        _kill_tree(process)


@contextlib.contextmanager
def killing_on_exit() -> Generator[None]:
    """Kill running member trees when grillspec ends, however it ends.

    Each member runs in its own process group, so it would outlive grillspec and
    keep spending quota. In the main thread this also handles SIGTERM and SIGHUP.

    Yields:
        None - While member processes may run.

    """
    restore: dict[int, object] = {}
    if threading.current_thread() is threading.main_thread():
        for name in ("SIGTERM", "SIGHUP"):
            number = cast("int | None", getattr(signal, name, None))
            if number is not None:
                restore[number] = signal.signal(number, _on_signal)
    try:
        yield
    finally:
        kill_all()
        for number, handler in restore.items():
            _ = signal.signal(number, cast("signal.Handlers", handler))


def _on_signal(signum: int, _frame: FrameType | None) -> None:
    """Kill member trees, then exit as the signal asked.

    Args:
        signum: int - The signal.
        _frame: FrameType | None - Unused.

    Raises:
        SystemExit: Always, with the conventional 128 + signal code.

    """
    kill_all()
    raise SystemExit(128 + signum)


_ = atexit.register(kill_all)


def _pump_in(pipe: IO[bytes], data: bytes) -> None:
    """Write the prompt and close stdin; a child that exits early is fine.

    Args:
        pipe: IO[bytes] - The child's stdin.
        data: bytes - What to send.

    """
    with contextlib.suppress(OSError):
        _ = pipe.write(data)
    with contextlib.suppress(OSError):
        pipe.close()


def _pump_out(pipe: io.BufferedReader, sink: bytearray) -> None:
    """Collect a pipe until it closes, then close our end.

    The pump closes the pipe itself: on Windows, closing a pipe another thread is
    still reading blocks until the leftover process that holds it exits, so
    ``run_tree`` may return while a pump still waits for such a process.

    Args:
        pipe: io.BufferedReader - The child's stdout or stderr.
        sink: bytearray - Where the bytes go.

    """
    try:
        with contextlib.suppress(OSError, ValueError):
            while chunk := pipe.read1(65_536):
                sink.extend(chunk)
    finally:
        with contextlib.suppress(OSError):
            pipe.close()


def _start(target: Callable[..., None], *args: object) -> threading.Thread:
    """Start a daemon thread.

    Returns:
        threading.Thread - The started thread.

    """
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return thread


def run_tree(
    argv: Sequence[str],
    *,
    stdin: bytes | None,
    timeout: float,
    cwd: Path | None = None,
) -> Finished:
    """Run a command without a shell, killing its whole tree at the timeout.

    Pipes are read on threads, so a child that leaves a background process
    holding stdout open is still done once it exits: its leftovers get
    ``LINGER_SECONDS`` and are then killed. An executable that cannot be started
    raises ``OSError`` from ``Popen``.

    Args:
        argv: Sequence[str] - Executable and arguments.
        stdin: bytes | None - Bytes to send and then close; None sends nothing.
        timeout: float - Seconds before the tree is killed.
        cwd: Path | None - Working directory; the current one when None.

    Returns:
        Finished - Exit code (None on timeout) and everything captured.

    """
    windows = sys.platform == "win32"
    # A new process group (Windows) or session (POSIX) lets the timeout kill the
    # whole tree, including what a ``.cmd`` shim or a node launcher started.
    new_group = cast("int", getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    # The argv is a resolved executable plus fixed flags; no shell is involved.
    # nosemgrep
    process = subprocess.Popen(
        list(argv),
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        creationflags=new_group if windows else 0,
        start_new_session=not windows,
    )
    with _LIVE_LOCK:
        _LIVE.add(process)
    out, err = bytearray(), bytearray()
    pumps = [
        _start(_pump_out, process.stdout, out),
        _start(_pump_out, process.stderr, err),
    ]
    if stdin is not None and process.stdin is not None:
        _ = _start(_pump_in, process.stdin, stdin)
    try:
        returncode: int | None = process.wait(timeout)
    except subprocess.TimeoutExpired:
        returncode = None
    try:
        if returncode is not None:
            for pump in pumps:
                pump.join(LINGER_SECONDS)
        if returncode is None or any(pump.is_alive() for pump in pumps):
            _kill_tree(process)
            drain = _DRAIN_SECONDS if returncode is None else _LEFTOVER_DRAIN_SECONDS
            for pump in pumps:
                pump.join(drain)
    finally:
        with _LIVE_LOCK:
            _LIVE.discard(process)
        with contextlib.suppress(subprocess.TimeoutExpired):
            _ = process.wait(_DRAIN_SECONDS)
    return Finished(returncode, bytes(out), bytes(err))
