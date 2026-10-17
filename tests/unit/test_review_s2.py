"""Regressions from the S2 final review."""

from __future__ import annotations

import datetime as dt
import tomllib
from typing import TYPE_CHECKING

import pytest

from grillspec.config import Backend, Config, ConfigError, CouncilMode
from grillspec.state import (
    ChangeError,
    Phase,
    Stage,
    approve,
    compute_status,
    create_change,
    open_questions,
    write_sidecar,
)
from support import write

if TYPE_CHECKING:
    from pathlib import Path

TODAY = dt.date(2026, 10, 17)
SP = Config(backend=Backend.SUPERPOWERS)


@pytest.mark.parametrize("slug", ["abc\n", "abc\n\n", "\nabc"])
def test_newline_slugs_are_refused(tmp_path: Path, slug: str):
    with pytest.raises(ChangeError, match="kebab-case"):
        create_change(tmp_path, SP, slug, today=TODAY)
    assert not any(tmp_path.rglob("*"))


def test_status_line_log_is_relative_and_escaped(tmp_path: Path):
    create_change(tmp_path, SP, "x", today=TODAY)
    status = compute_status(tmp_path, SP)
    assert status.log is not None
    assert not status.log.is_absolute()
    assert status.line().endswith("log=docs/grillspec/specs/2026-10-17-x.md")


def test_sidecar_quoted_keys_and_control_chars_round_trip(tmp_path: Path):
    path = tmp_path / "s.toml"
    data: dict[str, object] = {
        "version": 1,
        "my key": "v",
        "a.b": 1,
        "text": 'del\x7f tab\t quote" back\\slash юникод',
    }
    write_sidecar(path, data)
    assert tomllib.loads(path.read_text(encoding="utf-8")) == data


def test_approve_keeps_a_sidecar_with_quoted_keys_readable(tmp_path: Path):
    write(tmp_path / "docs/grillspec/specs/c1.md", "# c1\n")
    write(tmp_path / ".grillspec/changes/c1.toml", 'version = 1\n"my key" = "v"\n')
    write(tmp_path / ".grillspec/state.json", '{"version": 1, "active": "c1"}')
    approve(tmp_path, Backend.SUPERPOWERS, Stage.GRILL, today=TODAY)
    assert compute_status(tmp_path, SP).phase is Phase.SPEC


def test_council_default_comes_from_config(tmp_path: Path):
    config = Config(backend=Backend.SUPERPOWERS, council_enabled=CouncilMode.YES)
    change = create_change(tmp_path, config, "x", today=TODAY)
    assert change.log_path is not None
    assert "council=yes" in change.log_path.read_text()


def test_non_utf8_log_is_config_error(tmp_path: Path):
    log = tmp_path / "log.md"
    log.write_bytes("## Decision log\n- [ ] вопрос\n".encode("cp1251"))
    with pytest.raises(ConfigError, match=r"log\.md"):
        open_questions(log)


def test_zero_open_questions_says_confirm(tmp_path: Path):
    create_change(tmp_path, SP, "x", today=TODAY)
    status = compute_status(tmp_path, SP)
    assert status.next_step == "confirm the grill, then run grillspec approve grill"
