"""Tests for the session-start bootstrap (spec S1-R4)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from grillspec.cli import main
from grillspec.hooks import Harness, render_session_start, session_context
from support import write

if TYPE_CHECKING:
    from pathlib import Path

ROUTER_HEADING = "# Using grillspec"


def context_of(harness: Harness, payload: dict[str, object]) -> str:
    if harness in {Harness.CLAUDE, Harness.CODEX}:
        output = cast("dict[str, object]", payload["hookSpecificOutput"])
        assert output["hookEventName"] == "SessionStart"
        return str(output["additionalContext"])
    if harness is Harness.CURSOR:
        return str(payload["additional_context"])
    steps = cast("list[dict[str, dict[str, str]]]", payload["injectSteps"])
    return steps[0]["systemMessage"]["systemMessage"]


HOOKED = [Harness.CLAUDE, Harness.CODEX, Harness.CURSOR, Harness.ANTIGRAVITY]


@pytest.mark.parametrize("harness", HOOKED)
def test_shape_per_harness(harness: Harness, tmp_path: Path):  # S1-R4-S1
    payload = json.loads(render_session_start(harness, session_context(tmp_path)))
    text = context_of(harness, payload)
    assert ROUTER_HEADING in text
    assert "grillspec: phase=" in text
    assert "name: using-grillspec" not in text  # frontmatter stripped


def test_gigacode_has_no_hook():
    with pytest.raises(ValueError, match="gigacode"):
        render_session_start(Harness.GIGACODE, "x")


def run_hook(
    harness: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    code = main(["hook", "session-start", "--harness", harness])
    return code, json.loads(capsys.readouterr().out)


def test_cli_hook_outputs_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    code, payload = run_hook("claude", capsys)
    assert code == 0
    assert "grillspec: phase=idle" in context_of(Harness.CLAUDE, payload)


def test_crash_is_fail_open(  # S1-R4-S3
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)

    def boom(*_: object) -> None:
        msg = "disk on fire"
        raise RuntimeError(msg)

    monkeypatch.setattr("grillspec.hooks._session_start.compute_status", boom)
    code, payload = run_hook("cursor", capsys)
    text = context_of(Harness.CURSOR, payload)
    assert code == 0
    assert "grillspec bootstrap failed: RuntimeError: disk on fire" in text
    assert ROUTER_HEADING in text


def test_malformed_config_is_warning_in_context(  # Review Focus 1
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    write(tmp_path / ".grillspec/config.toml", "[grill\n")
    monkeypatch.chdir(tmp_path)
    code, payload = run_hook("codex", capsys)
    text = context_of(Harness.CODEX, payload)
    assert code == 0
    assert "config.toml" in text
    assert "WARNING" in text


def test_context_tells_how_to_run_the_cli(tmp_path: Path):
    text = session_context(tmp_path)
    line = next(line for line in text.splitlines() if line.startswith("grillspec CLI:"))
    assert "scripts" in line
    assert "grillspec" in line
