"""The journal: one SQLite file per project, searchable, never committed."""

from __future__ import annotations

import datetime as dt
import random
import re
import sqlite3
import time
import unicodedata
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast

from ._redact import redact

if TYPE_CHECKING:
    from collections.abc import Callable

NOTE_KINDS = ("handoff", "discovery", "blocker", "todo")
KINDS = ("event", *NOTE_KINDS)
_WORD = re.compile(r"\w+", re.UNICODE)
_MAX_ID = 2**63 - 1
_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL,
        change TEXT, text TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0,
        resolved INTEGER NOT NULL DEFAULT 0)""",
)
# A regular FTS5 table holding folded text, kept in step from Python: SQLite's
# tokenizer folds only Latin diacritics, and search must treat yo (U+0451) as ie.
_FTS_TABLE = "CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(text)"
_DROP_TRIGGERS = (
    "DROP TRIGGER IF EXISTS entries_ai",
    "DROP TRIGGER IF EXISTS entries_ad",
)
_HAS_FTS = "SELECT count(*) FROM sqlite_master WHERE name = 'entries_fts'"
_COUNTS = (
    "SELECT (SELECT count(*) FROM entries), (SELECT count(*) FROM entries_fts_docsize)"
)
_BUSY_SECONDS = 10.0
T = TypeVar("T")

_SELECT = "SELECT id, ts, kind, change, text, pinned, resolved FROM entries"
_RECENT = _SELECT + " ORDER BY ts DESC, id DESC LIMIT ?"
_PINNED = _SELECT + " WHERE pinned = 1 ORDER BY ts DESC, id DESC"
_BY_ID = _SELECT + " WHERE id = ?"
_ALL = _SELECT + " ORDER BY ts DESC, id DESC"
_MATCH = (
    "SELECT e.id, e.ts, e.kind, e.change, e.text, e.pinned, e.resolved "
    "FROM entries_fts JOIN entries AS e ON e.id = entries_fts.rowid "
    "WHERE entries_fts MATCH ? ORDER BY rank LIMIT ?"
)


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
        resolved: bool - A blocker or todo that no longer stands.

    """

    id: int
    ts: str
    kind: str
    change: str | None
    text: str
    pinned: bool
    resolved: bool = False


def _entry(row: tuple[object, ...]) -> Entry:
    id_, ts, kind, change, text, pinned, resolved = row
    return Entry(
        cast("int", id_),
        cast("str", ts),
        cast("str", kind),
        cast("str | None", change),
        cast("str", text),
        bool(pinned),
        bool(resolved),
    )


def _now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fold(text: str) -> str:
    """Fold text for search: case and diacritics, so yo (U+0451) reads as ie.

    Args:
        text: str - Any text.

    Returns:
        str - The folded text.

    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def main_root(root: Path) -> Path:
    """Return the project root that owns the journal.

    A git worktree (such as an execution worktree) shares the journal of the main
    working tree, when that tree is set up for grillspec.

    Args:
        root: Path - The project root grillspec found.

    Returns:
        Path - The main working tree's root, or ``root``.

    """
    dotgit = root / ".git"
    if not dotgit.is_file():
        return root
    try:
        text = dotgit.read_text(encoding="utf-8").strip()
    except OSError:
        return root
    if not text.startswith("gitdir:"):
        return root
    gitdir = Path(text.removeprefix("gitdir:").strip())
    gitdir = gitdir if gitdir.is_absolute() else (root / gitdir)
    common_file = gitdir / "commondir"
    try:
        common = (gitdir / common_file.read_text(encoding="utf-8").strip()).resolve()
    except OSError:
        return root
    main = common.parent if common.name == ".git" else None
    if main is not None and (main / ".grillspec").is_dir():
        return main
    return root


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


def _create_fts(con: sqlite3.Connection) -> bool:
    """Create the FTS5 index and bring it in step with the entries.

    Args:
        con: sqlite3.Connection - A connection inside a write transaction.

    Returns:
        bool - Whether FTS5 is in use (False when this SQLite lacks it).

    Raises:
        sqlite3.OperationalError: When the database is busy.

    """
    for statement in _DROP_TRIGGERS:
        _ = con.execute(statement)
    try:
        _ = con.execute(_FTS_TABLE)
        rows, indexed = cast("tuple[int, int]", con.execute(_COUNTS).fetchall()[0])
    except sqlite3.OperationalError as error:
        if _busy(error):
            raise
        return False
    if rows != indexed:  # entries written where FTS5 was missing or turned off
        _ = con.execute("DELETE FROM entries_fts")
        texts = cast(
            "list[tuple[int, str]]",
            con.execute("SELECT id, text FROM entries").fetchall(),
        )
        _ = con.executemany(
            "INSERT INTO entries_fts(rowid, text) VALUES (?, ?)",
            [(id_, fold(text)) for id_, text in texts],
        )
    return True


def _unindex(con: sqlite3.Connection, entry_id: int) -> None:
    """Drop an entry's folded copy from the index, if this SQLite can reach it.

    Raises:
        sqlite3.OperationalError: When the database is busy.

    """
    try:
        _ = con.execute("DELETE FROM entries_fts WHERE rowid = ?", (entry_id,))
        # Merge the segments, so no old segment still spells the deleted words.
        _ = con.execute("INSERT INTO entries_fts(entries_fts) VALUES ('optimize')")
    except sqlite3.OperationalError as error:
        if _busy(error):
            raise
        # No index here, or FTS5 missing: the next FTS-capable write rebuilds it.


def _setup(con: sqlite3.Connection, *, want_fts: bool | None) -> bool:
    """Create or migrate the tables, and the FTS5 index when wanted.

    Args:
        con: sqlite3.Connection - Open autocommit connection.
        want_fts: bool | None - False skips FTS5; None or True try it.

    Returns:
        bool - Whether FTS5 is in use.

    """
    _ = _retrying(lambda: con.execute("PRAGMA journal_mode=WAL").fetchall())
    _ = con.execute("PRAGMA secure_delete=ON")

    def create() -> bool:
        for statement in _SCHEMA:
            _ = con.execute(statement)
        columns = {
            cast("str", row[1])
            for row in cast(
                "list[tuple[object, ...]]",
                con.execute("PRAGMA table_info(entries)").fetchall(),
            )
        }
        if "resolved" not in columns:
            _ = con.execute(
                "ALTER TABLE entries ADD COLUMN resolved INTEGER NOT NULL DEFAULT 0"
            )
        return False if want_fts is False else _create_fts(con)

    return _transaction(con, create)


def _readable_fts(con: sqlite3.Connection) -> bool:
    """Tell whether a read may use the FTS5 index: present, loadable, complete.

    Args:
        con: sqlite3.Connection - A read connection.

    Returns:
        bool - True when ``MATCH`` queries return every entry they should.

    """
    try:
        present = cast("list[tuple[int]]", con.execute(_HAS_FTS).fetchall())[0][0]
        if not present:
            return False
        rows, indexed = cast("tuple[int, int]", con.execute(_COUNTS).fetchall()[0])
    except sqlite3.OperationalError:
        return False  # FTS5 missing in this Python, or an older index layout
    return rows == indexed


class Journal:
    """The project's journal in ``.grillspec/journal/memory.db``."""

    def __init__(self, root: Path, *, fts: bool | None = None) -> None:
        """Point at a project's journal; nothing is created until the first write.

        Args:
            root: Path - Project root (a worktree uses its main tree's journal).
            fts: bool | None - Force full-text search on or off; None detects it.

        """
        self.folder: Path = main_root(root) / ".grillspec" / "journal"
        self.path: Path = self.folder / "memory.db"
        self._want_fts: bool | None = fts
        self.fts: bool = False

    def _message(self, error: sqlite3.Error) -> str:
        return f"{self.path}: {error}"

    def _open_write(self) -> sqlite3.Connection:
        """Open (creating if needed) the store for a write, schema ready.

        Returns:
            sqlite3.Connection - An autocommit connection.

        Raises:
            JournalError: If SQLite refuses the file.

        """
        if not self.path.is_file():
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

    def _open_read(self) -> sqlite3.Connection | None:
        """Open the store read-only, without locks or schema changes.

        Returns:
            sqlite3.Connection | None - None when the store does not exist yet.

        Raises:
            JournalError: If the file is not a usable database.

        """
        if not self.path.is_file():
            return None
        uri = self.path.resolve().as_uri() + "?mode=ro"
        try:
            con = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
        except sqlite3.Error as error:
            raise JournalError(self._message(error)) from None
        self.fts = self._want_fts is not False and _readable_fts(con)
        return con

    def _rows(self, sql: str, params: tuple[object, ...] = ()) -> list[Entry]:
        con = self._open_read()
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

    def _write(self, work: Callable[[sqlite3.Connection], T]) -> T:
        con = self._open_write()
        with closing(con):
            try:
                return _transaction(con, lambda: work(con))
            except sqlite3.Error as error:
                raise JournalError(self._message(error)) from None

    def add(
        self,
        kind: str,
        text: str,
        *,
        change: str | None,
        ts: str | None = None,
        trusted: bool = False,
    ) -> Entry:
        """Store one entry, redacted unless grillspec wrote the text itself.

        Args:
            kind: str - One of ``KINDS``.
            text: str - The text.
            change: str | None - The active change.
            ts: str | None - UTC timestamp; now when None.
            trusted: bool - grillspec's own event text (change ids and fixed
                phrases), stored as is.

        Returns:
            Entry - The stored entry.

        Raises:
            JournalError: If the kind is unknown or SQLite fails.

        """
        if kind not in KINDS:
            msg = f"unknown kind {kind!r}; use one of {', '.join(KINDS)}"
            raise JournalError(msg)
        clean = (text if trusted else redact(text)).strip()
        stamp = ts or _now()

        def insert(con: sqlite3.Connection) -> int:
            row = con.execute(
                "INSERT INTO entries(ts, kind, change, text) VALUES (?, ?, ?, ?)",
                (stamp, kind, change, clean),
            ).lastrowid
            if self.fts:
                _ = con.execute(
                    "INSERT INTO entries_fts(rowid, text) VALUES (?, ?)",
                    (row, fold(clean)),
                )
            return cast("int", row)

        row = self._write(insert)
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
        if not 0 < entry_id <= _MAX_ID:
            return None
        found = self._rows(_BY_ID, (entry_id,))
        return found[0] if found else None

    def search(self, query: str, limit: int) -> list[Entry]:
        """Find entries containing every word of the query (words match prefixes).

        Args:
            query: str - Free text; operators and punctuation are ignored.
            limit: int - Maximum results.

        Returns:
            list[Entry] - Best matches first (FTS5 rank, else newest first).

        """
        words = cast("list[str]", _WORD.findall(fold(query)))
        if not words:
            return []
        con = self._open_read()
        if con is None:
            return []
        con.close()
        if self.fts:
            match = " ".join(f'"{word}"*' for word in words)
            return self._rows(_MATCH, (match, limit))
        everything = self._rows(_ALL)
        hits = [e for e in everything if all(w in fold(e.text) for w in words)]
        return hits[:limit]

    def _update(self, sql: str, params: tuple[object, ...]) -> None:
        _ = self._write(lambda con: con.execute(sql, params))

    def set_pinned(self, entry_id: int, *, flag: bool) -> None:
        """Pin or unpin an entry."""
        self._update(
            "UPDATE entries SET pinned = ? WHERE id = ?", (int(flag), entry_id)
        )

    def set_resolved(self, entry_id: int, *, flag: bool) -> None:
        """Mark a blocker or todo resolved, or open again."""
        self._update(
            "UPDATE entries SET resolved = ? WHERE id = ?", (int(flag), entry_id)
        )

    def forget(self, entry_id: int) -> None:
        """Delete an entry for good, leaving no copy in the file or its index.

        Raises:
            JournalError: If SQLite fails.

        """

        def delete(con: sqlite3.Connection) -> None:
            _ = con.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
            _unindex(con, entry_id)

        self._write(delete)
        con = self._open_write()
        with closing(con):
            try:
                _ = _retrying(lambda: con.execute("VACUUM"))
                _ = _retrying(
                    lambda: con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
                )
            except sqlite3.Error as error:
                raise JournalError(self._message(error)) from None
