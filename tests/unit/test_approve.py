"""Approvals and atomic sidecar writes (spec S2-R3)."""

from __future__ import annotations

import datetime as dt
import tomllib
from typing import TYPE_CHECKING

import pytest

from grillspec.cli import main
from grillspec.config import Backend, Config, ConfigError
from grillspec.state import (
    ChangeError,
    Phase,
    Stage,
    approve,
    compute_status,
    write_sidecar,
)
from support import write

if TYPE_CHECKING:
    from pathlib import Path

TODAY = dt.date(2026, 10, 17)
CONFIG = 'version = 1\n[spec]\nbackend = "superpowers"\n'


def project(root: Path, sidecar: str | None = "version = 1\n") -> Path:
    write(root / ".grillspec/config.toml", CONFIG)
    write(root / "docs/grillspec/specs/c1.md", "# c1\n\n## Decision log\n")
    if sidecar is not None:
        write(root / ".grillspec/changes/c1.toml", sidecar)
    write(root / ".grillspec/state.json", '{"version": 1, "active": "c1"}')
    return root / ".grillspec/changes/c1.toml"


def read(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_approve_grill_moves_to_spec(tmp_path: Path):  # S2-R3-S1
    sidecar = project(tmp_path)
    assert approve(tmp_path, Backend.SUPERPOWERS, Stage.GRILL, today=TODAY) == sidecar
    assert read(sidecar) == {"version": 1, "grilled": TODAY}
    status = compute_status(tmp_path, Config(backend=Backend.SUPERPOWERS))
    assert status.phase is Phase.SPEC


@pytest.mark.parametrize(
    ("stage", "key"),
    [(Stage.SPEC, "spec_approved"), (Stage.PLAN, "plan_approved")],
)
def test_approve_other_stages(tmp_path: Path, stage: Stage, key: str):
    sidecar = project(tmp_path)
    approve(tmp_path, Backend.SUPERPOWERS, stage, today=TODAY)
    assert read(sidecar)[key] == TODAY


def test_approve_without_sidecar_creates_it(tmp_path: Path):  # Review Focus 3
    project(tmp_path, sidecar=None)
    sidecar = approve(tmp_path, Backend.SUPERPOWERS, Stage.GRILL, today=TODAY)
    assert read(sidecar) == {"version": 1, "grilled": TODAY}


def test_unknown_keys_survive(tmp_path: Path):  # Review Focus 4
    sidecar = project(
        tmp_path, 'version = 1\nextra = "x \\"quoted\\""\ncount = 3\nflag = true\n'
    )
    approve(tmp_path, Backend.SUPERPOWERS, Stage.GRILL, today=TODAY)
    assert read(sidecar) == {
        "version": 1,
        "count": 3,
        "extra": 'x "quoted"',
        "flag": True,
        "grilled": TODAY,
    }
    assert sidecar.read_text().startswith("version = 1\n")


def test_no_active_change_errors(tmp_path: Path):
    write(tmp_path / ".grillspec/config.toml", CONFIG)
    with pytest.raises(ChangeError, match="no active change"):
        approve(tmp_path, Backend.SUPERPOWERS, Stage.GRILL, today=TODAY)


def test_write_sidecar_rejects_floats(tmp_path: Path):
    with pytest.raises(ConfigError):
        write_sidecar(tmp_path / "x.toml", {"version": 1, "ratio": 0.5})


def test_cli_approve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    project(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["approve", "grill"]) == 0
    assert "approved grill for c1" in capsys.readouterr().out
    (tmp_path / ".grillspec/state.json").unlink()
    assert main(["approve", "spec"]) == 1
    assert "no active change" in capsys.readouterr().err
