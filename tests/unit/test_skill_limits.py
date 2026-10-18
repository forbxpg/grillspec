"""Skills fit every harness's loader (Antigravity reads only 24,000 bytes of a body)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from support import REPO

if TYPE_CHECKING:
    from pathlib import Path

AGY_BODY_LIMIT = 24_000
SKILLS = sorted((REPO / "skills").glob("*/SKILL.md"))


@pytest.mark.parametrize("skill", SKILLS, ids=[path.parent.name for path in SKILLS])
def test_body_fits_antigravity(skill: Path):
    text = skill.read_bytes().replace(b"\r\n", b"\n")
    body = text.split(b"\n---\n", 1)[1] if text.startswith(b"---\n") else text
    assert len(body) <= AGY_BODY_LIMIT, (
        f"{skill.parent.name}: move detail to references"
    )
