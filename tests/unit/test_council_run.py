"""Tests for vendor adapters and the parallel council runner (spec S3-R3)."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from fakes import gone, make_fake, records
from grillspec.config import Member, parse_member
from grillspec.council import (
    INSTRUCTION,
    CouncilError,
    build_argv,
    parse_answer,
    run_members,
)

CONTRACT = {
    "options": [{"name": "A", "tradeoff": "t"}],
    "recommend": "A",
    "why": "w",
    "risks": [],
    "confidence": "high",
}
PROMPT = "the rendered prompt\nline two\n"


@pytest.mark.parametrize(
    ("spec", "tail"),
    [
        (
            "cli:claude",
            [
                "-p",
                "--tools",
                "",
                "--strict-mcp-config",
                "--no-session-persistence",
                "--setting-sources",
                "user",
                "--output-format",
                "json",
            ],
        ),
        (
            "cli:claude@opus",
            [
                "-p",
                "--tools",
                "",
                "--strict-mcp-config",
                "--no-session-persistence",
                "--setting-sources",
                "user",
                "--output-format",
                "json",
                "--model",
                "opus",
            ],
        ),
        (
            "cli:codex",
            ["exec", "--skip-git-repo-check", "-s", "read-only", "--ephemeral", "-"],
        ),
        (
            "cli:codex@gpt-5",
            [
                "exec",
                "--skip-git-repo-check",
                "-s",
                "read-only",
                "--ephemeral",
                "-m",
                "gpt-5",
                "-",
            ],
        ),
        (
            "cli:cursor-agent@sonnet-4",
            [
                "-p",
                "--trust",
                "--mode",
                "ask",
                "--output-format",
                "json",
                "--model",
                "sonnet-4",
            ],
        ),
        (
            "cli:gemini@gemini-2.5-pro",
            [
                "--approval-mode",
                "plan",
                "-o",
                "json",
                "-m",
                "gemini-2.5-pro",
                "-p",
                INSTRUCTION,
            ],
        ),
        ("cli:agy", ["--sandbox", "-p", INSTRUCTION]),
        (
            "cli:gigacode",
            [
                "-e",
                "none",
                "--no-chat-recording",
                "--approval-mode",
                "plan",
                "-o",
                "json",
                INSTRUCTION,
            ],
        ),
    ],
)
def test_argv_table(spec: str, tail: list[str]):
    assert build_argv(parse_member(spec), "/bin/x") == ["/bin/x", *tail]


def test_agy_model_refused():
    with pytest.raises(CouncilError, match="agy has no model option"):
        _ = build_argv(Member("cli", "agy", "m"), "agy")


def test_parse_answer_claude_error():
    stdout = json.dumps({"is_error": True, "result": "Credit balance too low"})
    text, model, error = parse_answer("claude", stdout)
    assert text == "Credit balance too low"
    assert model is None
    assert error == "claude reported an error: Credit balance too low"


def test_parse_answer_gemini_response_and_model():
    stdout = json.dumps({
        "response": "hello",
        "stats": {"models": {"gemini-2.5-pro": {}}},
    })
    assert parse_answer("gemini", stdout) == ("hello", "gemini-2.5-pro", None)


def test_parse_answer_unparseable_is_raw():
    assert parse_answer("claude", "not json") == ("not json", None, None)
    assert parse_answer("codex", "plain") == ("plain", None, None)


def test_parallel_with_hang(bin_dir: Path, tmp_path: Path):  # S3-R3-S1
    hung = tmp_path / "hung.jsonl"
    _ = make_fake(bin_dir, "codex", stdout=json.dumps(CONTRACT), sleep=1)
    _ = make_fake(
        bin_dir,
        "gemini",
        stdout=json.dumps({"response": json.dumps(CONTRACT)}),
        sleep=1,
    )
    _ = make_fake(bin_dir, "agy", sleep=60, spawn_child=True, record=hung)
    members = [parse_member(m) for m in ("cli:codex", "cli:gemini", "cli:agy")]
    started = time.monotonic()
    results = run_members(members, PROMPT, timeout=3, project_root=None)
    assert time.monotonic() - started < 5
    assert [r.name for r in results] == ["cli:codex", "cli:gemini", "cli:agy"]
    assert [r.ok for r in results] == [True, True, False]
    assert results[0].parsed == CONTRACT
    assert results[1].parsed == CONTRACT
    assert results[2].error == "timeout after 3s"
    (call,) = records(hung)
    assert isinstance(call["child_pid"], int)
    assert gone(call["child_pid"])


def test_member_sees_only_prompt(bin_dir: Path, tmp_path: Path):  # S3-R3-S3
    record = tmp_path / "rec.jsonl"
    shim = make_fake(bin_dir, "codex", stdout="ok", record=record)
    member = parse_member("cli:codex")
    (result,) = run_members([member], PROMPT, timeout=10, project_root=None)
    assert result.ok
    probe, call = records(record)
    assert probe["probe"] is True
    assert call["stdin"] == PROMPT
    assert call["argv"] == build_argv(member, str(shim))[1:]
    assert call["files"] == []
    cwd = Path(str(call["cwd"]))
    assert cwd.name.startswith("grillspec-council-")
    assert cwd.resolve().parent == Path(tempfile.gettempdir()).resolve()
    assert not cwd.exists()


def test_share_project_runs_in_root(bin_dir: Path, tmp_path: Path):
    record = tmp_path / "rec.jsonl"
    _ = make_fake(bin_dir, "agy", stdout="ok", record=record)
    project = tmp_path / "project"
    project.mkdir()
    _ = run_members([parse_member("cli:agy")], PROMPT, timeout=10, project_root=project)
    (call,) = records(record)
    assert Path(str(call["cwd"])).resolve() == project.resolve()


def test_claude_envelope_and_model(bin_dir: Path):
    envelope = {
        "type": "result",
        "is_error": False,
        "result": "Sure:\n```json\n" + json.dumps(CONTRACT) + "\n```",
        "modelUsage": {"claude-opus-test": {"inputTokens": 1}},
    }
    _ = make_fake(
        bin_dir,
        "claude",
        stdout=json.dumps(envelope),
        probe_stdout='{"loggedIn": true}',
    )
    (result,) = run_members(
        [parse_member("cli:claude")], PROMPT, timeout=10, project_root=None
    )
    assert result.ok
    assert result.parsed == CONTRACT
    assert result.model == "claude-opus-test"
    assert result.raw.startswith("Sure:")


def test_model_falls_back_to_override(bin_dir: Path):
    _ = make_fake(bin_dir, "codex", stdout="prose only")
    (result,) = run_members(
        [parse_member("cli:codex@gpt-5")], PROMPT, timeout=10, project_root=None
    )
    assert result.ok
    assert result.parsed is None
    assert result.raw == "prose only"
    assert result.model == "gpt-5"
    assert result.to_json() == {
        "name": "cli:codex@gpt-5",
        "model": "gpt-5",
        "ok": True,
        "ms": result.ms,
        "parsed": None,
        "raw": "prose only",
        "error": None,
    }


def test_exit_nonzero_reports_stderr_line(bin_dir: Path):  # Review Focus 4
    _ = make_fake(
        bin_dir, "codex", stderr="warming up\nERROR: 401 Unauthorized\n\n", exit_code=1
    )
    _ = make_fake(bin_dir, "agy", stdout="fine")
    failed, fine = run_members(
        [parse_member("cli:codex"), parse_member("cli:agy")],
        PROMPT,
        timeout=10,
        project_root=None,
    )
    assert not failed.ok
    assert failed.error == "exit 1: ERROR: 401 Unauthorized"
    assert fine.ok


def test_gemini_exit_41_is_auth(bin_dir: Path):
    _ = make_fake(bin_dir, "gemini", exit_code=41)
    (result,) = run_members(
        [parse_member("cli:gemini")], PROMPT, timeout=10, project_root=None
    )
    assert result.error == "not authenticated"


def test_huge_and_binary_output(bin_dir: Path):  # Review Focus 3
    _ = make_fake(bin_dir, "agy", stdout="\udcff" + "x" * 200_000)
    (result,) = run_members(
        [parse_member("cli:agy")], PROMPT, timeout=10, project_root=None
    )
    assert result.ok
    assert result.raw.startswith("�")
    assert result.raw.endswith("…[truncated]")
    assert len(result.raw) == 65_536 + len("…[truncated]")


def test_logged_out_member_not_run(bin_dir: Path, tmp_path: Path):
    record = tmp_path / "rec.jsonl"
    _ = make_fake(bin_dir, "codex", probe_exit=1, record=record)
    (result,) = run_members(
        [parse_member("cli:codex")], PROMPT, timeout=10, project_root=None
    )
    assert result.error == "not authenticated"
    assert [call["probe"] for call in records(record)] == [True]


def test_not_installed(bin_dir: Path):
    assert bin_dir.is_dir()
    (result,) = run_members(
        [parse_member("cli:claude")], PROMPT, timeout=10, project_root=None
    )
    assert not result.ok
    assert result.error == "not installed"
