"""Tests for locating bundled data."""

from __future__ import annotations

from grillspec.paths import data_root, template


def test_data_root_in_checkout_has_skills_hooks_templates():
    root = data_root()
    assert (root / "skills").is_dir()
    assert (root / "hooks").is_dir()
    assert (root / "templates").is_dir()


def test_template_reads_config_template():
    assert template("config.toml").startswith("version = 1\n")
