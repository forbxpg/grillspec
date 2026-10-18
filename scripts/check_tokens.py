"""Check, or refresh with --write, the generated token tables in the docs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grillspec.blocks import block_body, upsert_block
from grillspec.paths import data_root
from grillspec.tokens import Costs, measure, render_markdown

BEGIN = "<!-- grillspec:tokens:begin -->"
END = "<!-- grillspec:tokens:end -->"
LANGUAGES = ("en", "ru")


def stale(docs: Path, costs: Costs) -> list[Path]:
    """List the docs whose token table differs from the current estimates.

    Args:
        docs: Path - The ``docs`` folder.
        costs: Costs - Current estimates.

    Returns:
        list[Path] - Stale (or table-less) ``tokens.md`` files, English first.

    """
    found: list[Path] = []
    for language in LANGUAGES:
        path = docs / language / "tokens.md"
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        body = block_body(text, begin=BEGIN, end=END)
        if body != render_markdown(costs, language).split("\n"):
            found.append(path)
    return found


def refresh(docs: Path, costs: Costs) -> None:
    """Rewrite every docs token table from the current estimates.

    Args:
        docs: Path - The ``docs`` folder.
        costs: Costs - Current estimates.

    """
    for language in LANGUAGES:
        path = docs / language / "tokens.md"
        with path.open(encoding="utf-8", newline="") as handle:
            text = handle.read()
        new = upsert_block(text, render_markdown(costs, language), begin=BEGIN, end=END)
        with path.open("w", encoding="utf-8", newline="") as handle:
            _ = handle.write(new)


if __name__ == "__main__":
    folder = Path(__file__).resolve().parents[1] / "docs"
    estimates = measure(data_root(), None)
    if "--write" in sys.argv[1:]:
        refresh(folder, estimates)
    problems = stale(folder, estimates)
    for problem in problems:
        _ = sys.stdout.write(
            f"stale token table: {problem.relative_to(folder.parent)}\n"
        )
    if problems:
        _ = sys.stdout.write("run: uv run python scripts/check_tokens.py --write\n")
    sys.exit(1 if problems else 0)
