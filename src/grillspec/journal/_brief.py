"""The resume brief: what a new session needs, under a hard token cap."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grillspec.tokens import estimate

from ._store import Entry, Journal, JournalError

if TYPE_CHECKING:
    from pathlib import Path

    from grillspec.state import Status

BRIEF_TOKENS = 1500
_OPEN_LIMIT = 10
_RECENT_LIMIT = 20
_FOOTER = "More: grillspec recall <words>; pin a note with grillspec recall --pin <id>."
_EMPTY = (
    "Nothing recorded yet. Before this session ends, write a handoff note: "
    'grillspec note handoff -- "done: ...; next: ...; open: ...".'
)


def line(entry: Entry) -> str:
    """Render one entry as a brief or recall line.

    Returns:
        str - ``- [#<id> <kind> <date>] <text>``; a resolved note says so.

    """
    kind = f"{entry.kind} resolved" if entry.resolved else entry.kind
    return f"- [#{entry.id} {kind} {entry.ts[:10]}] {entry.text}"


def record_event(root: Path, change: str | None, text: str) -> str | None:
    """Record an event without ever failing the caller.

    Args:
        root: Path - Project root.
        change: str | None - The change the event belongs to.
        text: str - What happened.

    Returns:
        str | None - A warning when the journal could not be written, else None.

    """
    if not (root / ".grillspec").is_dir():
        return None
    body = f"{change}: {text}" if change else text
    try:
        _ = Journal(root).add("event", body, change=change, trusted=True)
    except (JournalError, OSError) as error:
        return str(error)
    return None


def _sections(journal: Journal) -> list[tuple[str, list[Entry]]]:
    recent = journal.recent(500)
    handoffs = [e for e in recent if e.kind == "handoff"][:1]
    open_notes = [
        e for e in recent if e.kind in {"blocker", "todo"} and not e.resolved
    ][:_OPEN_LIMIT]
    return [
        ("Pinned:", journal.pinned()),
        ("Last handoff:", handoffs),
        ("Open blockers and todos:", open_notes),
        # Older handoffs are superseded by the latest one: never repeat them.
        ("Recent:", [e for e in recent if e.kind != "handoff"][:_RECENT_LIMIT]),
    ]


def brief(root: Path, status: Status, cap_tokens: int = BRIEF_TOKENS) -> str:
    """Build the resume brief for a new session.

    Args:
        root: Path - Project root.
        status: Status - Current status (active change and phase).
        cap_tokens: int - Estimated-token limit for the whole brief.

    Returns:
        str - The brief; entries that do not fit are left out whole.

    """
    if status.change_id is None:
        head = "grillspec memory: no active change"
    else:
        head = f"grillspec memory: {status.change_id} in the {status.phase} phase"
    journal = Journal(root)
    try:
        sections = _sections(journal)
    except JournalError as error:
        return f"{head}\nThe journal is unreadable: {error}"
    if not any(entries for _, entries in sections):
        return f"{head}\n{_EMPTY}"
    lines = [head]
    budget = cap_tokens - estimate(_FOOTER) - 1
    shown: set[int] = set()
    for title, entries in sections:
        added: list[str] = []
        for entry in entries:
            if entry.id in shown:
                continue
            candidate = "\n".join([*lines, title, *added, line(entry)])
            if estimate(candidate) > budget:
                continue
            added.append(line(entry))
            shown.add(entry.id)
        if added:
            lines.extend([title, *added])
    return "\n".join([*lines, _FOOTER])
