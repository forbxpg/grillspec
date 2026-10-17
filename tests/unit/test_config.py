"""Tests for layered configuration (spec S1-R2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from grillspec.config import (
    Backend,
    ConfigError,
    CouncilMode,
    Depth,
    load_config,
    user_config_path,
)
from support import write

PROJECT = ".grillspec/config.toml"


def test_defaults_without_files(tmp_path: Path):
    loaded = load_config(tmp_path, user_path=tmp_path / "none.toml")
    cfg = loaded.config
    assert cfg.backend is None
    assert cfg.depth is Depth.STANDARD
    assert cfg.council_enabled is CouncilMode.ASK
    assert cfg.council_members == ()
    assert cfg.gates_enabled is True
    assert cfg.artifacts_language == "auto"
    assert loaded.warnings == ()


def test_project_overrides_user_per_key(tmp_path: Path):  # S1-R2-S1
    user = write(
        tmp_path / "u.toml",
        'version = 1\n[grill]\ndepth = "deep"\n[council]\nenabled = "no"\n',
    )
    write(tmp_path / PROJECT, 'version = 1\n[grill]\ndepth = "quick"\n')
    cfg = load_config(tmp_path, user_path=user).config
    assert cfg.depth is Depth.QUICK
    assert cfg.council_enabled is CouncilMode.NO


def test_all_keys_are_read(tmp_path: Path):
    write(
        tmp_path / PROJECT,
        """version = 1
[spec]
backend = "openspec"
artifacts_language = "ru"
[council]
enabled = "yes"
members = ["role:devil", "cli:gemini"]
[gates]
enabled = false
""",
    )
    cfg = load_config(tmp_path, user_path=tmp_path / "none.toml").config
    assert cfg.backend is Backend.OPENSPEC
    assert cfg.artifacts_language == "ru"
    assert cfg.council_enabled is CouncilMode.YES
    assert cfg.council_members == ("role:devil", "cli:gemini")
    assert cfg.gates_enabled is False


def test_unknown_key_warns(tmp_path: Path):  # S1-R2-S2
    write(tmp_path / PROJECT, "version = 1\n[grill]\nspeed = 3\n")
    loaded = load_config(tmp_path, user_path=tmp_path / "none.toml")
    assert any("grill.speed" in w and "config.toml" in w for w in loaded.warnings)


def test_invalid_value_names_key_file_and_allowed(tmp_path: Path):  # S1-R2-S3
    write(tmp_path / PROJECT, 'version = 1\n[grill]\ndepth = "extreme"\n')
    with pytest.raises(
        ConfigError, match=r"grill\.depth.*config\.toml.*quick, standard, deep"
    ):
        load_config(tmp_path, user_path=tmp_path / "none.toml")


def test_wrong_type_is_config_error(tmp_path: Path):
    write(tmp_path / PROJECT, "version = 1\n[gates]\nenabled = 1\n")
    with pytest.raises(ConfigError, match=r"gates\.enabled"):
        load_config(tmp_path, user_path=tmp_path / "none.toml")


def test_unsupported_version_is_config_error(tmp_path: Path):
    write(tmp_path / PROJECT, "version = 2\n")
    with pytest.raises(ConfigError, match=r"version"):
        load_config(tmp_path, user_path=tmp_path / "none.toml")


def test_malformed_toml_is_config_error_with_file(tmp_path: Path):  # Review Focus 1
    write(tmp_path / PROJECT, "[grill\n")
    with pytest.raises(ConfigError, match=r"config\.toml.*line 1"):
        load_config(tmp_path, user_path=tmp_path / "none.toml")


def test_user_path_prefers_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert user_config_path() == tmp_path / "grillspec" / "config.toml"


def test_user_path_appdata_on_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr("sys.platform", "win32")
    assert user_config_path() == tmp_path / "grillspec" / "config.toml"


def test_user_path_default_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert user_config_path() == tmp_path / ".config" / "grillspec" / "config.toml"
