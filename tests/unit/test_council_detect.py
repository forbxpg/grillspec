"""Tests for agent-CLI detection with authentication state (spec S3-R2)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from fakes import make_fake, records
from grillspec.cli import main
from grillspec.council import _vendors, auth_state
from grillspec.detect import CliStatus, cli_report

if TYPE_CHECKING:
    from pathlib import Path


def test_codex_logged_out(bin_dir: Path):  # S3-R2-S1
    shim = make_fake(bin_dir, "codex", probe_stdout="Not logged in\n", probe_exit=1)
    assert auth_state("codex", str(shim)) is False


def test_codex_logged_in(bin_dir: Path):
    shim = make_fake(bin_dir, "codex", probe_stdout="Logged in using ChatGPT\n")
    assert auth_state("codex", str(shim)) is True


def test_gigacode_text_probe(bin_dir: Path):  # S3-R2-S2
    shim = make_fake(
        bin_dir, "gigacode", probe_stdout="No authentication method configured.\n"
    )
    assert auth_state("gigacode", str(shim)) is False


def test_gigacode_other_text_is_unknown(bin_dir: Path):
    shim = make_fake(bin_dir, "gigacode", probe_stdout="Signed in\n")
    assert auth_state("gigacode", str(shim)) is None


@pytest.mark.parametrize(("logged_in", "expected"), [(True, True), (False, False)])
def test_claude_logged_in_json(bin_dir: Path, *, logged_in: bool, expected: bool):
    shim = make_fake(
        bin_dir, "claude", probe_stdout=json.dumps({"loggedIn": logged_in})
    )
    assert auth_state("claude", str(shim)) is expected


def test_claude_unparseable_is_unknown(bin_dir: Path):
    shim = make_fake(bin_dir, "claude", probe_stdout="hello")
    assert auth_state("claude", str(shim)) is None


def test_cursor_agent_json(bin_dir: Path):
    shim = make_fake(
        bin_dir, "cursor-agent", probe_stdout=json.dumps({"isAuthenticated": True})
    )
    assert auth_state("cursor-agent", str(shim)) is True


def test_gemini_unknown_without_key(bin_dir: Path):
    shim = make_fake(bin_dir, "gemini")
    assert auth_state("gemini", str(shim)) is None


def test_gemini_key_env(bin_dir: Path, monkeypatch: pytest.MonkeyPatch):
    shim = make_fake(bin_dir, "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert auth_state("gemini", str(shim)) is True


def test_gemini_login_file(bin_dir: Path, tmp_path: Path):
    shim = make_fake(bin_dir, "gemini")
    creds = tmp_path / "home" / ".gemini" / "oauth_creds.json"
    creds.parent.mkdir()
    _ = creds.write_text("{}", encoding="utf-8")
    assert auth_state("gemini", str(shim)) is True


def test_agy_is_unknown(bin_dir: Path):
    shim = make_fake(bin_dir, "agy")
    assert auth_state("agy", str(shim)) is None


def test_probe_hang_is_unknown(bin_dir: Path, monkeypatch: pytest.MonkeyPatch):
    shim = make_fake(bin_dir, "codex")
    # A probe that never answers: replace the script with one that sleeps.
    script = bin_dir / "_codex_fake.py"
    _ = script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    monkeypatch.setattr(_vendors, "PROBE_TIMEOUT", 1)
    assert auth_state("codex", str(shim)) is None


def test_probe_gets_no_stdin(bin_dir: Path, tmp_path: Path):
    record = tmp_path / "rec.jsonl"
    shim = make_fake(bin_dir, "codex", record=record)
    _ = auth_state("codex", str(shim))
    (call,) = records(record)
    assert call["probe"] is True
    assert not call["stdin"]


def test_cli_report_only_probes_installed(bin_dir: Path):
    _ = make_fake(bin_dir, "codex", probe_exit=1)
    report = cli_report()
    assert list(report) == [
        "claude",
        "codex",
        "cursor-agent",
        "gemini",
        "agy",
        "gigacode",
    ]
    assert report["codex"] == CliStatus(
        installed=True, authenticated=False, experimental=False
    )
    assert report["claude"] == CliStatus(
        installed=False, authenticated=None, experimental=False
    )
    assert report["gigacode"].experimental is True


def test_detect_json_shape(
    bin_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    _ = make_fake(bin_dir, "codex")
    monkeypatch.chdir(tmp_path)
    assert main(["detect", "--json"]) == 0
    clis = json.loads(capsys.readouterr().out)["clis"]
    assert clis["codex"] == {
        "installed": True,
        "authenticated": True,
        "experimental": False,
    }
    assert clis["gemini"] == {
        "installed": False,
        "authenticated": None,
        "experimental": False,
    }


def test_detect_text_line(
    bin_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    _ = make_fake(bin_dir, "codex", probe_exit=1)
    _ = make_fake(bin_dir, "claude", probe_stdout='{"loggedIn": true}')
    _ = make_fake(bin_dir, "gemini")
    monkeypatch.chdir(tmp_path)
    assert main(["detect"]) == 0
    assert (
        "agent CLIs: claude (logged in), codex (not logged in), gemini (auth unknown)"
        in capsys.readouterr().out
    )
