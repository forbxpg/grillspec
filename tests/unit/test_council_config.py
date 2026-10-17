"""Tests for the council configuration keys (spec S3-R1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grillspec.config import ConfigError, External, Member, load_config, parse_member
from support import write

if TYPE_CHECKING:
    from pathlib import Path

PROJECT = ".grillspec/config.toml"


def test_defaults(tmp_path: Path):
    cfg = load_config(tmp_path, user_path=tmp_path / "none.toml").config
    assert cfg.council_external is External.ALLOW
    assert cfg.council_timeout == 120
    assert cfg.council_share_project is False


def test_project_never_wins(tmp_path: Path):  # S3-R1-S1
    user = write(
        tmp_path / "u.toml", 'version = 1\n[council]\nmembers = ["cli:codex"]\n'
    )
    write(tmp_path / PROJECT, 'version = 1\n[council]\nexternal = "never"\n')
    cfg = load_config(tmp_path, user_path=user).config
    assert cfg.council_members == ("cli:codex",)
    assert cfg.council_external is External.NEVER


def test_user_never_wins_over_project_allow(tmp_path: Path):
    user = write(tmp_path / "u.toml", 'version = 1\n[council]\nexternal = "never"\n')
    write(tmp_path / PROJECT, 'version = 1\n[council]\nexternal = "allow"\n')
    cfg = load_config(tmp_path, user_path=user).config
    assert cfg.council_external is External.NEVER


@pytest.mark.parametrize(
    "member",
    ["cli:foo", "role:bar", "cli:codex@", "cli:claude@a&calc", "cli:codex@--yolo"],
)
def test_bad_member_names_key_file_forms(tmp_path: Path, member: str):  # S3-R1-S2
    path = write(
        tmp_path / PROJECT, f'version = 1\n[council]\nmembers = ["{member}"]\n'
    )
    with pytest.raises(ConfigError) as caught:
        _ = load_config(tmp_path, user_path=tmp_path / "none.toml")
    message = str(caught.value)
    assert "council.members" in message
    assert str(path) in message
    assert "cli:<vendor>[@<model>]" in message


def test_member_with_model():
    assert parse_member("cli:gemini@gemini-2.5-pro") == Member(
        "cli", "gemini", "gemini-2.5-pro"
    )
    assert parse_member("role:devil") == Member("role", "devil", None)
    assert parse_member("cli:cursor-agent") == Member("cli", "cursor-agent", None)


@pytest.mark.parametrize("value", ["0", "601", "true", '"120"'])
def test_timeout_rejected(tmp_path: Path, value: str):
    write(tmp_path / PROJECT, f"version = 1\n[council]\ntimeout = {value}\n")
    with pytest.raises(ConfigError, match=r"council\.timeout"):
        _ = load_config(tmp_path, user_path=tmp_path / "none.toml")


def test_timeout_and_share_project_read(tmp_path: Path):
    write(
        tmp_path / PROJECT,
        "version = 1\n[council]\ntimeout = 600\nshare_project = true\n",
    )
    cfg = load_config(tmp_path, user_path=tmp_path / "none.toml").config
    assert cfg.council_timeout == 600
    assert cfg.council_share_project is True
