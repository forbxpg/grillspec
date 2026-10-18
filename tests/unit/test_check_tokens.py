"""Tests for the generated token table check (spec S9-R2)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from grillspec.paths import data_root
from grillspec.tokens import measure, render_markdown
from support import write

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "check_tokens", REPO / "scripts" / "check_tokens.py"
)
assert _spec is not None
assert _spec.loader is not None
check_tokens = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_tokens)

BEGIN = "<!-- grillspec:tokens:begin -->"
END = "<!-- grillspec:tokens:end -->"


def _docs(root: Path, table: dict[str, str]) -> Path:
    for language, body in table.items():
        write(
            root / language / "tokens.md",
            f"# Tokens\n\n{BEGIN}\n{body}\n{END}\n\nAfter.\n",
        )
    return root


def test_fresh_tables_pass(tmp_path: Path):
    costs = measure(data_root(), None)
    docs = _docs(
        tmp_path, {lang: render_markdown(costs, lang) for lang in ("en", "ru")}
    )
    assert check_tokens.stale(docs, costs) == []


def test_stale_tables_named(tmp_path: Path):  # TK-4
    costs = measure(data_root(), None)
    docs = _docs(tmp_path, {"en": "| old |", "ru": "| old |"})
    assert check_tokens.stale(docs, costs) == [
        docs / "en/tokens.md",
        docs / "ru/tokens.md",
    ]
    check_tokens.refresh(docs, costs)
    assert check_tokens.stale(docs, costs) == []
    assert (docs / "en/tokens.md").read_text(encoding="utf-8").endswith("\n\nAfter.\n")


def test_crlf_doc_is_not_stale(tmp_path: Path):  # Review Focus 2
    costs = measure(data_root(), None)
    docs = _docs(
        tmp_path, {lang: render_markdown(costs, lang) for lang in ("en", "ru")}
    )
    for language in ("en", "ru"):
        path = docs / language / "tokens.md"
        _ = path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert check_tokens.stale(docs, costs) == []


def test_russian_table_is_russian():
    table = render_markdown(measure(data_root(), None), "ru")
    assert table.startswith("| Часть |")


def test_repository_docs_are_fresh():
    assert check_tokens.stale(REPO / "docs", measure(data_root(), None)) == []
