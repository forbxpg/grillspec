"""Fixes from the S3 final review: CLI resolution, process lifetime, --out."""

from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING, cast

import pytest

from fakes import gone, make_fake, records
from grillspec.cli import main
from grillspec.config import ConfigError, load_config, parse_member
from grillspec.council import resolve_cli, run_members
from support import write

if TYPE_CHECKING:
    from pathlib import Path

PAYLOAD = json.dumps({
    "version": 1,
    "question": "Retry policy?",
    "options": ["backoff", "fixed"],
    "settled": [],
    "context": "",
})


def test_cli_in_cwd_but_not_on_path_is_not_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bin_dir: Path
):
    repo = tmp_path / "repo"
    _ = make_fake(repo, "codex")
    monkeypatch.chdir(repo)
    assert bin_dir.is_dir()
    assert resolve_cli("codex") is None


def test_relative_path_entries_are_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo = tmp_path / "repo"
    _ = make_fake(repo / "bin", "codex")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", "bin")
    assert resolve_cli("codex") is None


def test_absolute_path_entry_resolves(bin_dir: Path):
    shim = make_fake(bin_dir, "codex")
    found = resolve_cli("codex")
    assert found is not None
    # Windows matches PATHEXT case-insensitively (codex.CMD finds codex.cmd).
    assert os.path.normcase(found) == os.path.normcase(str(shim))


def test_answer_with_lingering_child_is_ok(bin_dir: Path, tmp_path: Path):
    record = tmp_path / "rec.jsonl"
    _ = make_fake(
        bin_dir, "agy", stdout='{"recommend": "A"}', spawn_child=True, record=record
    )
    started = time.monotonic()
    (result,) = run_members(
        [parse_member("cli:agy")], "p", timeout=20, project_root=None
    )
    assert time.monotonic() - started < 8
    assert result.ok, result.error
    assert result.parsed == {"recommend": "A"}
    if sys.platform != "win32":
        # Windows cannot reach a grandchild once its parent has exited.
        (call,) = records(record)
        assert gone(cast("int", call["child_pid"]))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_sigterm_kills_member_trees(bin_dir: Path, tmp_path: Path):
    record = tmp_path / "rec.jsonl"
    _ = make_fake(bin_dir, "agy", sleep=60, spawn_child=True, record=record)
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    payload = write(tmp_path / "q.json", PAYLOAD)
    argv = ["council", "ask", "--members", "cli:agy", "--payload", str(payload)]
    proc = subprocess.Popen(
        [sys.executable, "-m", "grillspec", *argv],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        env=env,
    )
    deadline = time.monotonic() + 20
    while not records(record) and time.monotonic() < deadline:
        time.sleep(0.1)
    (call,) = records(record)
    proc.send_signal(signal.SIGTERM)
    _ = proc.communicate(timeout=15)
    assert gone(cast("int", call["pid"]))
    assert gone(cast("int", call["child_pid"]))


def test_out_file_written_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bin_dir: Path
):
    _ = make_fake(bin_dir, "agy", stdout="x")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO(PAYLOAD))
    out = tmp_path / ".grillspec/council/Q1.out.json"
    assert main(["council", "ask", "--members", "cli:agy", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["members"][0]["raw"] == "x"


def test_out_file_gets_the_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[council]\nexternal = "never"\n',
    )
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "Q1.out.json"
    assert main(["council", "ask", "--members", "cli:agy", "--out", str(out)]) == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert 'council.external = "never"' in data["error"]
    assert 'council.external = "never"' in capsys.readouterr().err


def test_out_file_gets_council_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "Q1.out.json"
    assert main(["council", "ask", "--members", "role:devil", "--out", str(out)]) == 1
    assert "role members run as subagents" in json.loads(out.read_text())["error"]


def test_agy_model_refused_at_config_load(tmp_path: Path):
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[council]\nmembers = ["cli:agy@m"]\n',
    )
    with pytest.raises(ConfigError, match="agy has no model option"):
        _ = load_config(tmp_path, user_path=tmp_path / "none.toml")
