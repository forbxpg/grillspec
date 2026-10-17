"""Tests for the skill frontmatter and router size lint (spec S1-R5)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from support import write

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "lint_skills", REPO / "scripts" / "lint_skills.py"
)
assert _spec is not None
assert _spec.loader is not None
lint_skills = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint_skills)
lint = lint_skills.lint


def skill(root: Path, name: str, front: str, body: str = "# Body\n") -> None:
    write(root / name / "SKILL.md", f"---\n{front}---\n\n{body}")


def test_valid_skill_passes(tmp_path: Path):
    skill(tmp_path, "alpha", "name: alpha\ndescription: Use when testing.\n")
    assert lint(tmp_path) == []


def test_extra_frontmatter_key_fails(tmp_path: Path):
    skill(tmp_path, "alpha", "name: alpha\ndescription: d\nmodel: opus\n")
    assert any("model" in error for error in lint(tmp_path))


def test_missing_description_fails(tmp_path: Path):
    skill(tmp_path, "alpha", "name: alpha\n")
    assert any("description" in error for error in lint(tmp_path))


def test_name_must_match_dir(tmp_path: Path):
    skill(tmp_path, "alpha", "name: beta\ndescription: d\n")
    assert any("alpha" in error and "beta" in error for error in lint(tmp_path))


def test_description_over_1024_fails(tmp_path: Path):
    skill(tmp_path, "alpha", f"name: alpha\ndescription: {'x' * 1025}\n")
    assert any("1024" in error for error in lint(tmp_path))


def test_router_over_150_lines_fails(tmp_path: Path):
    body = "line\n" * 151
    skill(tmp_path, "using-grillspec", "name: using-grillspec\ndescription: d\n", body)
    assert any("150" in error for error in lint(tmp_path))


def test_repo_skills_pass():
    assert lint(REPO / "skills") == []


def test_folder_without_skill_md_fails(tmp_path: Path):
    skill(tmp_path, "alpha", "name: alpha\ndescription: d\n")
    (tmp_path / "beta").mkdir()
    assert any("beta" in error and "SKILL.md" in error for error in lint(tmp_path))


def test_multiline_description_is_rejected(tmp_path: Path):
    skill(tmp_path, "alpha", "name: alpha\ndescription: >-\n  folded text\n")
    errors = lint(tmp_path)
    assert any("single line" in error for error in errors)


def test_empty_quoted_description_fails(tmp_path: Path):
    skill(tmp_path, "alpha", 'name: alpha\ndescription: ""\n')
    assert any("missing description" in error for error in lint(tmp_path))


def test_quoted_values_are_unquoted(tmp_path: Path):
    skill(tmp_path, "alpha", "name: \"alpha\"\ndescription: 'Use when x.'\n")
    assert lint(tmp_path) == []


def test_repo_skill_names_are_prefixed():
    names = sorted(p.name for p in (REPO / "skills").iterdir() if p.is_dir())
    assert all(n == "using-grillspec" or n.startswith("grillspec-") for n in names), (
        names
    )
