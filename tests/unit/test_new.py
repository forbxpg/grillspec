"""grillspec new (spec S2-R2)."""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING

import pytest

from grillspec.cli import main
from grillspec.config import Backend, Config, Depth
from grillspec.state import ChangeError, Phase, compute_status, create_change
from support import write

if TYPE_CHECKING:
    from pathlib import Path

TODAY = dt.date(2026, 10, 17)
SP = Config(backend=Backend.SUPERPOWERS)
OS = Config(backend=Backend.OPENSPEC)


def tree(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_superpowers_id_and_skeleton(tmp_path: Path):  # S2-R2-S1
    change = create_change(tmp_path, SP, "rate-limits", today=TODAY)
    assert change.id == "2026-10-17-rate-limits"
    log = tmp_path / "docs/grillspec/specs/2026-10-17-rate-limits.md"
    assert log.read_text() == (
        "# 2026-10-17-rate-limits\n\n## Decision log\n\n"
        "<!-- grillspec: depth=standard council=no budget=15 asked=0 -->\n\n"
        "### Open\n\n### Settled\n"
    )
    assert (
        tmp_path / ".grillspec/changes/2026-10-17-rate-limits.toml"
    ).read_text() == "version = 1\n"
    status = compute_status(tmp_path, SP)
    assert (status.phase, status.change_id, status.open_questions) == (
        Phase.GRILL,
        "2026-10-17-rate-limits",
        0,
    )


def test_openspec_skeleton(tmp_path: Path):  # S2-R2-S2
    create_change(tmp_path, OS, "add-rate-limits", today=TODAY)
    folder = tmp_path / "openspec/changes/add-rate-limits"
    assert (
        (folder / "design.md")
        .read_text()
        .startswith("# Design: add-rate-limits\n\n## Decision log\n")
    )
    assert (
        folder / ".openspec.yaml"
    ).read_text() == "schema: spec-driven\ncreated: 2026-10-17\n"


def test_refuse_silent_switch(tmp_path: Path):  # S2-R2-S3
    create_change(tmp_path, SP, "first", today=TODAY)
    before = tree(tmp_path)
    with pytest.raises(ChangeError, match=r"2026-10-17-first.*grill"):
        create_change(tmp_path, SP, "second", today=TODAY)
    assert tree(tmp_path) == before


def test_switch_flag_allows(tmp_path: Path):
    create_change(tmp_path, SP, "first", today=TODAY)
    change = create_change(tmp_path, SP, "second", today=TODAY, switch=True)
    assert compute_status(tmp_path, SP).change_id == change.id


def test_existing_id_refused(tmp_path: Path):  # S2-R2-S4
    create_change(tmp_path, SP, "dup", today=TODAY)
    with pytest.raises(ChangeError, match="exists"):
        create_change(tmp_path, SP, "dup", today=TODAY, switch=True)


def test_archived_id_refused(tmp_path: Path):  # S2-R2-S4
    write(tmp_path / "openspec/changes/archive/2026-01-01-old/proposal.md", "x\n")
    with pytest.raises(ChangeError, match="archived"):
        create_change(tmp_path, OS, "old", today=TODAY)
    assert not (tmp_path / "openspec/changes/old").exists()


@pytest.mark.parametrize(
    "slug", ["../x", "Rate_Limits", "лимиты", "a--b", "-a", "a-", ""]
)
def test_bad_slugs(tmp_path: Path, slug: str):  # S2-R2-S5, Review Focus 5
    with pytest.raises(ChangeError, match="kebab-case"):
        create_change(tmp_path, SP, slug, today=TODAY)
    assert tree(tmp_path) == set()


@pytest.mark.parametrize(
    ("depth", "budget"),
    [(Depth.QUICK, "5"), (Depth.STANDARD, "15"), (Depth.DEEP, "none")],
)
def test_metadata_line_budget_by_depth(tmp_path: Path, depth: Depth, budget: str):
    change = create_change(tmp_path, SP, "x", today=TODAY, depth=depth, council=True)
    assert change.log_path is not None
    assert (
        f"depth={depth} council=yes budget={budget} asked=0"
        in change.log_path.read_text()
    )


def test_requires_backend(tmp_path: Path):
    with pytest.raises(ChangeError, match="grillspec init"):
        create_change(tmp_path, Config(), "x", today=TODAY)


def test_cli_new(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "superpowers"\n',
    )
    monkeypatch.chdir(tmp_path)
    assert main(["new", "rate-limits", "--depth", "deep", "--council"]) == 0
    out = capsys.readouterr().out
    assert "rate-limits" in out
    assert "docs/grillspec/specs/" in out
    assert main(["new", "other"]) == 1
    assert "--switch" in capsys.readouterr().err
    assert main(["status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["phase"] == "grill"


def test_council_metadata_has_calls_counter(tmp_path: Path):
    config = Config(backend=Backend.SUPERPOWERS)
    with_council = create_change(
        tmp_path, config, "a", today=dt.date(2026, 10, 17), council=True
    )
    assert with_council.log_path is not None
    assert "council=yes budget=15 asked=0 council_calls=0 -->" in (
        with_council.log_path.read_text(encoding="utf-8")
    )
    without = create_change(
        tmp_path, config, "b", today=dt.date(2026, 10, 17), switch=True
    )
    assert without.log_path is not None
    assert "council_calls" not in without.log_path.read_text(encoding="utf-8")
