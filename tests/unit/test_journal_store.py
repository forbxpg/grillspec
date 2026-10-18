"""Tests for the session-memory journal store (spec JR-R1, JR-R3)."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from typing import TYPE_CHECKING

import pytest

from grillspec.journal import Journal, redact

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(params=[True, False], ids=["fts5", "like"])
def journal(request: pytest.FixtureRequest, tmp_path: Path) -> Journal:
    return Journal(tmp_path, fts=bool(request.param))


def test_first_write_creates_an_ignored_store(tmp_path: Path):  # JR-1
    folder = tmp_path / ".grillspec" / "journal"
    assert not folder.exists()
    journal = Journal(tmp_path)
    assert journal.recent(5) == []  # reading creates nothing
    assert not folder.exists()
    entry = journal.add("handoff", "next: wire the retry queue", change="add-retries")
    assert (folder / "memory.db").is_file()
    assert (folder / ".gitignore").read_text(encoding="utf-8") == "*\n"
    assert journal.recent(5) == [entry]
    assert entry.kind == "handoff"
    assert entry.change == "add-retries"
    assert entry.ts.endswith("Z")
    assert not entry.pinned


def test_search_finds_words(journal: Journal):  # JR-2 (like) and FTS5
    _ = journal.add("discovery", "the webhook client retries on 502 only", change=None)
    _ = journal.add("todo", "document the cache expiry", change=None)
    found = journal.search("retries webhook", 10)
    assert [e.text for e in found] == ["the webhook client retries on 502 only"]


def test_russian_search(journal: Journal):  # JR-3
    text = "ретраи с экспоненциальной задержкой"  # ruff: ignore[ambiguous-unicode-character-string]
    _ = journal.add("discovery", text, change=None)
    assert len(journal.search("задержкой", 10)) == 1
    assert len(journal.search("ЗАДЕРЖКОЙ", 10)) == 1


@pytest.mark.parametrize("query", ['"', "*", "-x", "a:b", "(", "NEAR", "", "   "])
def test_odd_queries_never_raise(journal: Journal, query: str):  # Review Focus 2
    _ = journal.add("todo", "a b x NEAR", change=None)
    assert isinstance(journal.search(query, 10), list)


def test_pin_forget(journal: Journal):
    first = journal.add("discovery", "old but important", change=None)
    _ = journal.add("todo", "newer", change=None)
    journal.set_pinned(first.id, flag=True)
    assert [e.id for e in journal.pinned()] == [first.id]
    journal.forget(first.id)
    assert journal.pinned() == []
    assert journal.search("important", 10) == []


def test_fts_is_detected(tmp_path: Path):
    journal = Journal(tmp_path)
    _ = journal.add("todo", "x", change=None)
    with closing(sqlite3.connect(":memory:")) as con:
        try:
            _ = con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
            available = True
        except sqlite3.OperationalError:
            available = False
    assert journal.fts is available


def test_concurrent_writers(tmp_path: Path):  # Review Focus 1
    errors: list[BaseException] = []

    def write(n: int) -> None:
        try:
            for i in range(20):
                _ = Journal(tmp_path).add("todo", f"writer {n} note {i}", change=None)
        except BaseException as error:  # ruff: ignore[blind-except] - collected for the assertion
            errors.append(error)

    threads = [threading.Thread(target=write, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(Journal(tmp_path).recent(1000)) == 80


def test_secret_never_stored(journal: Journal):  # JR-6
    entry = journal.add(
        "discovery",
        "export OPENAI_KEY=sk-test-4f9a2c7e and <private>pin 1234</private> done",
        change=None,
    )
    assert "sk-test" not in entry.text
    assert "1234" not in entry.text
    assert "<redacted>" in entry.text
    assert journal.search("pin", 10) == []


@pytest.mark.parametrize(
    "secret",
    [
        "ghp_" + "a" * 36,
        "github_pat_" + "B" * 30,
        "xoxb-1234567890-abcdefghij",
        "AKIAIOSFODNN7EXAMPLE",
        "glpat-" + "c" * 20,
        "Bearer abcdefghijklmnop1234",
        ".".join(("eyJ" + "h" * 16, "eyJ" + "p" * 16, "dozjgN" + "s" * 16)),
        "password=hunter22",
        "token: abc123def456",
        "DB_" + "PASSWORD" + "=" + "s3cr3t",  # built: no literal for secret scanners
    ],
)
def test_redact_patterns(secret: str):  # JR-R3
    text = redact(f"before {secret} after")
    assert "<redacted>" in text
    assert text.startswith("before ")
    assert text.endswith(" after")
    for fragment in (
        "aaaa",
        "BBBB",
        "abcdefghij",
        "IOSFODNN",
        "cccc",
        "hunter22",
        "abc123",
        "s3cr3t",
        "dozjgN",
    ):
        assert fragment not in text


def test_redact_pem_and_unclosed_private():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----"
    assert "MIIEow" not in redact(f"key {pem} end")
    assert redact("keep <private>drop this") == "keep "
    assert redact("plain words stay") == "plain words stay"


def test_fts_ranks_better_matches_first(tmp_path: Path):
    journal = Journal(tmp_path, fts=True)
    _ = journal.add("todo", "cache cache cache expiry", change=None)
    _ = journal.add("todo", "retry queue with a small cache", change=None)
    if not journal.fts:
        pytest.skip("this Python's SQLite has no FTS5")
    assert journal.search("retry cache", 10)[0].text == "retry queue with a small cache"
