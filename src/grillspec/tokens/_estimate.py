"""Token estimates from UTF-8 sizes, calibrated against a measured session."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from grillspec.blocks import block_body
from grillspec.memory import MEMORY_BEGIN, MEMORY_END

if TYPE_CHECKING:
    from pathlib import Path

# 9,524 bytes of injected router, status line and skill catalogue cost 2,092 input
# tokens in Claude Code 2.1.287 on 2026-10-18 (with vs without the plugin).
BYTES_PER_TOKEN = 4.5
_FIELD = re.compile(r"^(name|description):\s*(.*?)\s*$", re.MULTILINE)
ROUTER = "using-grillspec"
# What session start adds after the router body, as in a fresh project; fixed so the
# estimate does not depend on where grillspec is installed.
STATUS_SAMPLE = (
    "grillspec: phase=idle change=- next=run grillspec init\n"
    "grillspec CLI: grillspec <command>"
)


@dataclass(frozen=True)
class SkillCost:
    """What one skill costs when it is used.

    Attributes:
        name: str - Skill name.
        body: int - ``SKILL.md`` without its frontmatter, loaded on activation.
        references: int - The other files in the skill's folder, read only when
            the skill points the agent to them.

    """

    name: str
    body: int
    references: int


@dataclass(frozen=True)
class Costs:
    """grillspec's context costs, in estimated tokens.

    Attributes:
        router: int - Session-start injection: router body and status line.
        catalogue: int - Every skill's name and description, listed each session.
        memory: int | None - The project's memory block, when measured and present.
        skills: tuple[SkillCost, ...] - Per skill, by name.

    """

    router: int
    catalogue: int
    memory: int | None
    skills: tuple[SkillCost, ...]

    @property
    def always_on(self) -> int:
        """What every session pays: router, catalogue and memory block."""
        return self.router + self.catalogue + (self.memory or 0)


def estimate(text: str) -> int:
    """Estimate the tokens of a text from its UTF-8 size.

    Args:
        text: str - The text.

    Returns:
        int - ``ceil(bytes / BYTES_PER_TOKEN)``.

    """
    return math.ceil(len(text.encode("utf-8")) / BYTES_PER_TOKEN)


def _skill(folder: Path) -> tuple[SkillCost, str, str]:
    """Measure one skill folder.

    Args:
        folder: Path - The folder holding ``SKILL.md``.

    Returns:
        tuple[SkillCost, str, str] - Its costs, its catalogue line and its body.

    """
    text = (folder / "SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    front, _, body = text.removeprefix("---\n").partition("\n---\n")
    fields: dict[str, str] = {
        str(key): str(value)
        for key, value in cast("list[tuple[str, str]]", _FIELD.findall(front))
    }
    name = fields.get("name", folder.name)
    others = (
        p for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "SKILL.md"
    )
    references = sum(
        estimate(p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n"))
        for p in others
    )
    line = f"- {name}: {fields.get('description', '')}"
    return SkillCost(name, estimate(body.strip()), references), line, body.strip()


def _memory(project: Path) -> int | None:
    agents = project / "AGENTS.md"
    if not agents.is_file():
        return None
    text = agents.read_text(encoding="utf-8").replace("\r\n", "\n")
    body = block_body(text, begin=MEMORY_BEGIN, end=MEMORY_END)
    return (
        None if body is None else estimate("\n".join([MEMORY_BEGIN, *body, MEMORY_END]))
    )


def measure(data_root: Path, project: Path | None) -> Costs:
    """Estimate grillspec's context costs from its installed files.

    Args:
        data_root: Path - Where grillspec's ``skills/`` live.
        project: Path | None - A project whose memory block to include.

    Returns:
        Costs - The estimates.

    """
    measured = [
        _skill(p.parent) for p in sorted((data_root / "skills").glob("*/SKILL.md"))
    ]
    skills = tuple(sorted((cost for cost, _, _ in measured), key=lambda s: s.name))
    catalogue = estimate("\n".join(line for _, line, _ in measured))
    body = next((text for cost, _, text in measured if cost.name == ROUTER), "")
    router = estimate(f"{body}\n\n{STATUS_SAMPLE}")
    memory = _memory(project) if project is not None else None
    return Costs(router, catalogue, memory, skills)


def render_markdown(costs: Costs) -> str:
    """Render the cost table the docs embed.

    Args:
        costs: Costs - The estimates.

    Returns:
        str - A Markdown table with LF newlines and no trailing newline.

    """
    every = "every session"
    count = len(costs.skills)
    rows = [
        "| Part | When it is loaded | ≈ tokens |",
        "|---|---|---|",
        f"| router and status line | {every} (hook harnesses) | {costs.router:,} |",
        f"| skill catalogue ({count} skills) | {every} | {costs.catalogue:,} |",
    ]
    rows.extend(
        f"| `{s.name}` | when the skill is used | {s.body:,}"
        + (f" (+{s.references:,} in references)" if s.references else "")
        + " |"
        for s in costs.skills
    )
    return "\n".join(rows)
