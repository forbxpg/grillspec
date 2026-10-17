"""Tests for ``grillspec council ask`` (spec S3-R3)."""

from __future__ import annotations

import io
import json
import sys
from typing import TYPE_CHECKING, cast

import pytest

from fakes import make_fake, records
from grillspec.cli import main
from support import write

if TYPE_CHECKING:
    from pathlib import Path

PAYLOAD = json.dumps({
    "version": 1,
    "question": "Retry policy?",
    "options": ["backoff", "fixed"],
    "settled": [],
    "context": "queue sender",
})


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


def _config(root: Path, council: str) -> None:
    write(
        root / ".grillspec/config.toml",
        f'version = 1\n[spec]\nbackend = "superpowers"\n[council]\n{council}\n',
    )


def _out(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    return cast("dict[str, object]", json.loads(capsys.readouterr().out))


def _members(out: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", out["members"])


def test_ask_runs_members_and_prints_json(
    project: Path, bin_dir: Path, capsys: pytest.CaptureFixture[str]
):
    _ = make_fake(bin_dir, "codex", stdout='{"recommend": "backoff"}')
    _ = make_fake(bin_dir, "agy", stdout="prose")
    assert main(["council", "ask", "--members", "cli:codex,cli:agy"]) == 0
    out = _out(capsys)
    assert out["version"] == 1
    members = _members(out)
    assert [m["name"] for m in members] == ["cli:codex", "cli:agy"]
    assert members[0]["parsed"] == {"recommend": "backoff"}
    assert members[1]["parsed"] is None
    assert project.is_dir()


def test_never_exits_1_without_processes(  # S3-R3-S4
    project: Path,
    bin_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    record = tmp_path / "rec.jsonl"
    _ = make_fake(bin_dir, "codex", record=record)
    _config(project, 'external = "never"\nmembers = ["cli:codex"]')
    assert main(["council", "ask"]) == 1
    assert records(record) == []
    assert 'council.external = "never"' in capsys.readouterr().err
    assert sys.stdin.read() == PAYLOAD  # stdin was not even read


def test_dry_run_starts_nothing(  # S3-R3-S5
    project: Path,
    bin_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    record = tmp_path / "rec.jsonl"
    _ = make_fake(bin_dir, "codex", record=record)
    assert (
        main(["council", "ask", "--members", "cli:codex,cli:gemini@g-1", "--dry-run"])
        == 0
    )
    assert records(record) == []
    out = _out(capsys)
    assert out["dry_run"] is True
    members = _members(out)
    codex, gemini = members
    assert codex["name"] == "cli:codex"
    codex_argv = cast("list[str]", codex["argv"])
    gemini_argv = cast("list[str]", gemini["argv"])
    assert codex_argv[-1] == "-"
    assert gemini_argv[0] == "gemini"
    assert "-m" in gemini_argv
    assert codex["cwd"] == "<new empty temp dir>"
    assert "Retry policy?" in cast("str", codex["prompt"])
    assert codex["prompt"] == gemini["prompt"]
    assert project.is_dir()


def test_share_project_dry_run_cwd(project: Path, capsys: pytest.CaptureFixture[str]):
    _config(project, "share_project = true")
    assert main(["council", "ask", "--members", "cli:agy", "--dry-run"]) == 0
    members = _members(_out(capsys))
    assert members[0]["cwd"] == str(project)


def test_role_in_members_flag_refused(
    project: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["council", "ask", "--members", "role:devil,cli:codex"]) == 1
    assert "role members run as subagents" in capsys.readouterr().err
    assert project.is_dir()


def test_bad_member_in_flag_refused(project: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["council", "ask", "--members", "cli:codex@--yolo"]) == 1
    assert "not a council member" in capsys.readouterr().err
    assert project.is_dir()


def test_duplicates_collapsed(  # Review Focus 5
    project: Path, bin_dir: Path, capsys: pytest.CaptureFixture[str]
):
    _ = make_fake(bin_dir, "agy", stdout="x")
    assert main(["council", "ask", "--members", "cli:agy, cli:agy"]) == 0
    members = _members(_out(capsys))
    assert [m["name"] for m in members] == ["cli:agy"]
    assert project.is_dir()


def test_config_members_used_and_roles_dropped(
    project: Path, bin_dir: Path, capsys: pytest.CaptureFixture[str]
):
    _ = make_fake(bin_dir, "agy", stdout="x")
    _config(project, 'members = ["role:devil", "cli:agy"]')
    assert main(["council", "ask"]) == 0
    members = _members(_out(capsys))
    assert [m["name"] for m in members] == ["cli:agy"]


def test_no_external_members_exit_1(  # Review Focus 5
    project: Path, capsys: pytest.CaptureFixture[str]
):
    _config(project, 'members = ["role:devil"]')
    assert main(["council", "ask"]) == 1
    assert (
        "no external council members (role members run as subagents)"
        in capsys.readouterr().err
    )


def test_bad_payload_one_line_error(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"version": 1}'))
    assert main(["council", "ask", "--members", "cli:agy"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("grillspec: council payload: question")
    assert err.count("\n") == 1
    assert project.is_dir()


def test_agy_model_refused_before_running(
    project: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["council", "ask", "--members", "cli:agy@m1"]) == 1
    assert "agy has no model option" in capsys.readouterr().err
    assert project.is_dir()


def test_timeout_flag_overrides_config(
    project: Path, bin_dir: Path, capsys: pytest.CaptureFixture[str]
):
    _ = make_fake(bin_dir, "agy", stdout="late", sleep=5)
    _config(project, "timeout = 100")
    assert main(["council", "ask", "--members", "cli:agy", "--timeout", "1"]) == 0
    members = _members(_out(capsys))
    assert members[0]["error"] == "timeout after 1s"


def test_timeout_flag_bounds(project: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["council", "ask", "--members", "cli:agy", "--timeout", "0"]) == 1
    assert "--timeout" in capsys.readouterr().err
    assert project.is_dir()


def test_payload_read_as_utf8_whatever_the_locale(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    text = PAYLOAD.replace("Retry policy?", "Политика повторов?")
    stdin = io.TextIOWrapper(io.BytesIO(text.encode()), encoding="cp1252")
    monkeypatch.setattr(sys, "stdin", stdin)
    assert main(["council", "ask", "--members", "cli:agy", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert out.isascii()
    members = _members(cast("dict[str, object]", json.loads(out)))
    assert "Политика повторов?" in cast("str", members[0]["prompt"])
    assert project.is_dir()


def test_payload_from_file(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    path = write(
        project / ".grillspec/council/Q1.json",
        PAYLOAD.replace("Retry policy?", "Политика?"),
    )
    assert (
        main([
            "council",
            "ask",
            "--members",
            "cli:agy",
            "--payload",
            str(path),
            "--dry-run",
        ])
        == 0
    )
    members = _members(_out(capsys))
    assert "Политика?" in cast("str", members[0]["prompt"])


def test_payload_file_missing(project: Path, capsys: pytest.CaptureFixture[str]):
    assert (
        main(["council", "ask", "--members", "cli:agy", "--payload", "nope.json"]) == 1
    )
    assert "nope.json" in capsys.readouterr().err
    assert project.is_dir()
