"""The journal: one SQLite file per project, searchable, never committed."""

from __future__ import annotations

import datetime as dt
import random
import re
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar, cast

from ._redact import redact

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

NOTE_KINDS = ("handoff", "discovery", "blocker", "todo")
KINDS = ("event", *NOTE_KINDS)
_WORD = re.compile(r"\w+", re.UNICODE)
_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL,
        change TEXT, text TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0)""",
)
_FTS = (
    """CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
        text, content='entries', content_rowid='id',
        tokenize='unicode61 remove_diacritics 2')""",
    """CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
        INSERT INTO entries_fts(rowid, text) VALUES (new.id, new.text); END""",
    """CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
        INSERT INTO entries_fts(entries_fts, rowid, text)
        VALUES ('delete', old.id, old.text); END""",
)
_BUSY_SECONDS = 10.0
T = TypeVar("T")
_COLUMNS = "id, ts, kind, change, text, pinned"


class JournalError(Exception):
    """The journal cannot be read or written."""


@dataclass(frozen=True)
class Entry:
    """One journal entry.

    Attributes:
        id: int - Row id.
        ts: str - UTC time, ISO 8601 with a ``Z``.
        kind: str - One of ``KINDS``.
        change: str | None - The active change when it was written.
        text: str - Redacted text.
        pinned: bool - Always included in the brief.

    """

    id: int
    ts: str
    kind: str
    change: str | None
    text: str
    pinned: bool


def _entry(row: tuple[object, ...]) -> Entry:
    id_, ts, kind, change, text, pinned = row
    return Entry(
        cast("int", id_),
        cast("str", ts),
        cast("str", kind),
        cast("str | None", change),
        cast("str", text),
        bool(pinned),
    )


def _now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


_SELECT = "SELECT id, ts, kind, change, text, pinned FROM entries"
_RECENT = _SELECT + " ORDER BY ts DESC, id DESC LIMIT ?"
_PINNED = _SELECT + " WHERE pinned = 1 ORDER BY ts DESC, id DESC"
_BY_ID = _SELECT + " WHERE id = ?"
_ALL = _SELECT + " ORDER BY ts DESC, id DESC"
_MATCH = (
    "SELECT e.id, e.ts, e.kind, e.change, e.text, e.pinned FROM entries_fts "
    "JOIN entries AS e ON e.id = entries_fts.rowid "
    "WHERE entries_fts MATCH ? ORDER BY rank LIMIT ?"
)
_UNINDEXED = (
    "SELECT count(*) FROM entries WHERE id NOT IN (SELECT rowid FROM entries_fts)"
)


def _busy(error: sqlite3.OperationalError) -> bool:
    text = str(error).lower()
    return "locked" in text or "busy" in text


def _retrying(action: Callable[[], T]) -> T:
    """Run an action, retrying while another connection holds the lock.

    Args:
        action: Callable[[], T] - The work.

    Returns:
        T - Its result.

    Raises:
        sqlite3.OperationalError: When the lock outlasts ``_BUSY_SECONDS``, or on any
            other operational error.

    """
    deadline = time.monotonic() + _BUSY_SECONDS
    delay = 0.01
    while True:
        try:
            return action()
        except sqlite3.OperationalError as error:
            if not _busy(error) or time.monotonic() > deadline:
                raise
            time.sleep(delay + random.uniform(0, delay))  # ruff: ignore[suspicious-non-cryptographic-random-usage] - jitter, not crypto
            delay = min(delay * 2, 0.2)


def _transaction(con: sqlite3.Connection, work: Callable[[], T]) -> T:
    """Run work inside ``BEGIN IMMEDIATE`` so the write lock is taken up front.

    Args:
        con: sqlite3.Connection - An autocommit connection.
        work: Callable[[], T] - The statements.

    Returns:
        T - What the work returns; a failure rolls the transaction back and
            propagates.

    """

    def attempt() -> T:
        _ = con.execute("BEGIN IMMEDIATE")
        try:
            result = work()
        except BaseException:
            _ = con.execute("ROLLBACK")
            raise
        _ = con.execute("COMMIT")
        return result

    return _retrying(attempt)


def _setup(con: sqlite3.Connection, *, want_fts: bool | None) -> bool:
    """Create the tables, and the FTS5 index when wanted and available.

    Args:
        con: sqlite3.Connection - Open autocommit connection.
        want_fts: bool | None - False skips FTS5; None or True try it.

    Returns:
        bool - Whether FTS5 is in use.

    """
    _ = _retrying(lambda: con.execute("PRAGMA journal_mode=WAL").fetchall())

    def create() -> bool:
        for statement in _SCHEMA:
            _ = con.execute(statement)
        if want_fts is False:
            return False
        try:
            for statement in _FTS:
                _ = con.execute(statement)
        except sqlite3.OperationalError as error:
            if _busy(error):
                raise
            return False
        missing = cast("list[tuple[int]]", con.execute(_UNINDEXED).fetchall())
        if missing[0][0]:
            _ = con.execute("INSERT INTO entries_fts(entries_fts) VALUES ('rebuild')")
        return True

    return _transaction(con, create)


class Journal:
    """The project's journal in ``.grillspec/journal/memory.db``."""

    def __init__(self, root: Path, *, fts: bool | None = None) -> None:
        """Point at a project's journal; nothing is created until the first write.

        Args:
            root: Path - Project root.
            fts: bool | None - Force full-text search on or off; None detects it.

        """
        self.folder: Path = root / ".grillspec" / "journal"
        self.path: Path = self.folder / "memory.db"
        self._want_fts: bool | None = fts
        self.fts: bool = False

    def _message(self, error: sqlite3.Error) -> str:
        return f"{self.path}: {error}"

    def _connect(self, *, create: bool) -> sqlite3.Connection | None:
        """Open the database, creating it (and its ignore file) when asked.

        Args:
            create: bool - Create the store when it does not exist.

        Returns:
            sqlite3.Connection | None - None when it does not exist and is not created.

        Raises:
            JournalError: If SQLite refuses the file.

        """
        if not self.path.is_file():
            if not create:
                return None
            self.folder.mkdir(parents=True, exist_ok=True)
            ignore = self.folder / ".gitignore"
            if not ignore.is_file():
                _ = ignore.write_text("*\n", encoding="utf-8")
        try:
            con = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        except sqlite3.Error as error:
            raise JournalError(self._message(error)) from None
        try:
            self.fts = _setup(con, want_fts=self._want_fts)
        except sqlite3.Error as error:
            con.close()
            raise JournalError(self._message(error)) from None
        return con

    def _rows(self, sql: str, params: tuple[object, ...] = ()) -> list[Entry]:
        con = self._connect(create=False)
        if con is None:
            return []
        with closing(con):
            try:
                rows = cast(
                    "list[tuple[object, ...]]", con.execute(sql, params).fetchall()
                )
            except sqlite3.Error as error:
                raise JournalError(self._message(error)) from None
        return [_entry(row) for row in rows]

    def _write(self, sql: str, params: tuple[object, ...]) -> int:
        con = self._connect(create=True)
        if con is None:  # create=True always connects
            return 0
        with closing(con):
            try:
                return _transaction(
                    con, lambda: con.execute(sql, params).lastrowid or 0
                )
            except sqlite3.Error as error:
                raise JournalError(self._message(error)) from None

    def add(
        self, kind: str, text: str, *, change: str | None, ts: str | None = None
    ) -> Entry:
        """Store one entry after redaction.

        Args:
            kind: str - One of ``KINDS``.
            text: str - The text; private spans and secrets are removed first.
            change: str | None - The active change.
            ts: str | None - UTC timestamp; now when None.

        Returns:
            Entry - The stored entry.

        Raises:
            JournalError: If the kind is unknown or SQLite fails.

        """
        if kind not in KINDS:
            msg = f"unknown kind {kind!r}; use one of {', '.join(KINDS)}"
            raise JournalError(msg)
        clean = redact(text).strip()
        stamp = ts or _now()
        row = self._write(
            "INSERT INTO entries(ts, kind, change, text) VALUES (?, ?, ?, ?)",
            (stamp, kind, change, clean),
        )
        return Entry(row, stamp, kind, change, clean, pinned=False)

    def recent(self, limit: int) -> list[Entry]:
        """Return the newest entries first.

        Returns:
            list[Entry] - Up to ``limit`` entries.

        """
        return self._rows(_RECENT, (limit,))

    def pinned(self) -> list[Entry]:
        """Return pinned entries, newest first.

        Returns:
            list[Entry] - Every pinned entry.

        """
        return self._rows(_PINNED)

    def get(self, entry_id: int) -> Entry | None:
        """Return one entry by id.

        Returns:
            Entry | None - The entry, or None.

        """
        found = self._rows(_BY_ID, (entry_id,))
        return found[0] if found else None

    def search(self, query: str, limit: int) -> list[Entry]:
        """Find entries containing every word of the query.

        Args:
            query: str - Free text; operators and punctuation are ignored.
            limit: int - Maximum results.

        Returns:
            list[Entry] - Best matches first (FTS5 rank, else newest first).

        """
        words = cast("list[str]", _WORD.findall(query))
        if not words:
            return []
        _ = self._rows(_RECENT, (0,))  # connects, so self.fts is known
        if self.fts:
            match = " ".join(f'"{word}"' for word in words)
            return self._rows(_MATCH, (match, limit))
        folded = [word.casefold() for word in words]
        everything = self._rows(_ALL)
        hits = [e for e in everything if all(w in e.text.casefold() for w in folded)]
        return hits[:limit]

    def set_pinned(self, entry_id: int, *, flag: bool) -> None:
        """Pin or unpin an entry."""
        _ = self._write(
            "UPDATE entries SET pinned = ? WHERE id = ?", (int(flag), entry_id)
        )

    def forget(self, entry_id: int) -> None:
        """Delete an entry for good."""
        _ = self._write("DELETE FROM entries WHERE id = ?", (entry_id,))
