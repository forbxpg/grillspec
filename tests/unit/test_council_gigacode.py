"""Tests for the council on a machine where GigaCode is the only agent CLI."""

from __future__ import annotations

import io
import json
import sys
from typing import TYPE_CHECKING, cast

import pytest

from fakes import make_fake, records
from grillspec.cli import main
from grillspec.config import parse_member
from grillspec.council import INSTRUCTION, auth_state, build_argv
from grillspec.detect import CliStatus, cli_report, council_defaults
from support import write

if TYPE_CHECKING:
    from pathlib import Path

ROLES = ["role:simplicity", "role:devil", "role:risk"]
LOGGED_OUT = (
    "\n=== Authentication Status ===\n\n"
    "⚠️  No authentication method configured.\n\n"
    "Run one of the following commands to get started:\n"
)
LOGGED_IN = (
    "\n=== Authentication Status ===\n\n"
    "✓ Authentication Method: gigacode\n  Status: Configured\n"
)
LOGGED_OUT_RU = (
    "\n=== Статус аутентификации ===\n\n⚠️  Метод аутентификации не настроен.\n"
)
PAYLOAD = json.dumps({
    "version": 1,
    "question": "Retry policy?",
    "options": ["backoff", "fixed"],
    "settled": [],
    "context": "queue sender",
})


def _status(
    *, installed: bool = True, authenticated: bool | None = None, experimental: bool
) -> CliStatus:
    return CliStatus(
        installed=installed, authenticated=authenticated, experimental=experimental
    )


def test_only_gigacode_installed(bin_dir: Path):  # GC-1
    _ = make_fake(bin_dir, "gigacode")
    assert council_defaults(cli_report()) == [*ROLES, "cli:gigacode"]


def test_gigacode_logged_out_is_left_out(bin_dir: Path):  # GC-2
    _ = make_fake(bin_dir, "gigacode", probe_stdout=LOGGED_OUT)
    assert council_defaults(cli_report()) == ROLES


def test_first_class_cli_wins(bin_dir: Path):  # GC-3
    _ = make_fake(bin_dir, "codex", probe_stdout="Logged in using ChatGPT\n")
    _ = make_fake(bin_dir, "gigacode")
    assert council_defaults(cli_report()) == [*ROLES, "cli:codex"]


def test_logged_out_first_class_cli_lets_gigacode_in():
    report = {
        "codex": _status(authenticated=False, experimental=False),
        "claude": _status(installed=False, experimental=False),
        "gigacode": _status(authenticated=True, experimental=True),
    }
    assert council_defaults(report) == [*ROLES, "cli:gigacode"]


def test_nothing_installed_is_roles_only(bin_dir: Path):
    assert bin_dir.is_dir()
    assert council_defaults(cli_report()) == ROLES


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bin_dir: Path) -> Path:
    assert bin_dir.is_dir()
    root = tmp_path / "project"
    write(
        root / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "superpowers"\n',
    )
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "stdin", io.StringIO(PAYLOAD))
    return root


def test_council_ask_uses_gigacode_by_default(  # GC-4
    project: Path, bin_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    log = tmp_path / "calls.jsonl"
    answer = json.dumps([
        {"type": "system", "subtype": "init"},
        {"type": "result", "result": '{"recommend": "backoff"}', "is_error": False},
    ])
    _ = make_fake(bin_dir, "gigacode", stdout=answer, record=log)
    assert main(["council", "ask"]) == 0
    out = cast("dict[str, object]", json.loads(capsys.readouterr().out))
    members = cast("list[dict[str, object]]", out["members"])
    assert [m["name"] for m in members] == ["cli:gigacode"]
    assert members[0]["parsed"] == {"recommend": "backoff"}
    calls = [c for c in records(log) if not c["probe"]]
    assert len(calls) == 1
    assert project.is_dir()


def test_council_ask_without_any_cli_fails(
    project: Path, capsys: pytest.CaptureFixture[str]
):
    assert project.is_dir()
    assert main(["council", "ask"]) == 1
    assert "no external council members" in capsys.readouterr().err


def test_detect_lists_council_defaults(  # GC-5
    bin_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    _ = make_fake(bin_dir, "gigacode")
    monkeypatch.chdir(tmp_path)
    assert main(["detect", "--json"]) == 0
    out = cast("dict[str, object]", json.loads(capsys.readouterr().out))
    assert out["council"] == [*ROLES, "cli:gigacode"]


def test_gigacode_argv_is_isolated():  # GC-6
    argv = build_argv(parse_member("cli:gigacode@GigaChat-2-Max"), "/bin/gigacode")
    assert argv == [
        "/bin/gigacode",
        "-e",
        "none",
        "--no-chat-recording",
        "--approval-mode",
        "plan",
        "-o",
        "json",
        "-m",
        "GigaChat-2-Max",
        INSTRUCTION,
    ]


@pytest.mark.parametrize(
    ("probe", "expected"),
    [(LOGGED_IN, True), (LOGGED_OUT, False), (LOGGED_OUT_RU, False)],
    ids=["logged-in", "logged-out", "logged-out-ru"],
)
def test_gigacode_probe(bin_dir: Path, probe: str, *, expected: bool):  # GC-7
    shim = make_fake(bin_dir, "gigacode", probe_stdout=probe)
    assert auth_state("gigacode", str(shim)) is expected
