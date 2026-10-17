"""The decision a council is asked about, and the prompt each member reads."""

from __future__ import annotations

import json
import secrets
import string
from dataclasses import dataclass
from typing import cast

from grillspec.paths import data_root

PAYLOAD_VERSION = 1
PROMPT = ("skills", "grillspec-council", "references", "prompt.md")


class CouncilError(Exception):
    """A council request cannot be carried out as given."""


@dataclass(frozen=True)
class Payload:
    """One decision put to the council.

    Attributes:
        question: str - The decision, as put to the user.
        options: tuple[str, ...] - The options on the table.
        settled: tuple[str, ...] - Decisions it depends on, already made.
        context: str - Facts the grilling agent wrote down, without secrets.

    """

    question: str
    options: tuple[str, ...]
    settled: tuple[str, ...]
    context: str


def _strings(data: dict[str, object], key: str) -> tuple[str, ...]:
    """Read a list of strings from the payload.

    Args:
        data: dict[str, object] - Decoded payload.
        key: str - Field name.

    Returns:
        tuple[str, ...] - The list.

    Raises:
        CouncilError: If the field is not a list of strings.

    """
    value = data.get(key)
    items = cast("list[object]", value) if isinstance(value, list) else None
    if items is None or not all(isinstance(item, str) for item in items):
        msg = f"council payload: {key} must be a list of strings"
        raise CouncilError(msg)
    return tuple(cast("list[str]", items))


def parse_payload(text: str) -> Payload:
    """Parse and validate a council payload.

    Args:
        text: str - JSON ``{version: 1, question, options, settled, context}``.

    Returns:
        Payload - The decision.

    Raises:
        CouncilError: If the text is not such an object; the message names the
            first bad field.

    """
    try:
        decoded = cast("object", json.loads(text))
    except ValueError as error:
        msg = f"council payload is not JSON: {error}"
        raise CouncilError(msg) from None
    if not isinstance(decoded, dict):
        msg = "council payload must be a JSON object"
        raise CouncilError(msg)
    data = cast("dict[str, object]", decoded)
    version = data.get("version")
    if type(version) is not int or version != PAYLOAD_VERSION:
        msg = f"council payload: version must be 1, not {version!r}"
        raise CouncilError(msg)
    question = data.get("question")
    if not isinstance(question, str) or not question.strip():
        msg = "council payload: question must be a non-empty string"
        raise CouncilError(msg)
    options = _strings(data, "options")
    settled = _strings(data, "settled")
    context = data.get("context")
    if not isinstance(context, str):
        msg = "council payload: context must be a string"
        raise CouncilError(msg)
    return Payload(question, options, settled, context)


def render_prompt(payload: Payload, *, nonce: str | None = None) -> str:
    """Render the prompt an external member reads.

    The payload sits inside ``<data-NONCE>`` tags; a fresh random nonce per call
    means text inside the payload cannot close the data block. External members
    answer without a role lens, so the ``Lens:`` line is dropped.

    Args:
        payload: Payload - The decision.
        nonce: str | None - Delimiter nonce; random when None.

    Returns:
        str - The prompt.

    """
    raw = (data_root().joinpath(*PROMPT)).read_text(encoding="utf-8")
    template = "".join(
        line for line in raw.splitlines(keepends=True) if "$lens" not in line
    )
    options = "\n".join(f"{n}. {option}" for n, option in enumerate(payload.options, 1))
    settled = "\n".join(f"- {item}" for item in payload.settled)
    return string.Template(template).substitute(
        nonce=nonce or secrets.token_hex(8),
        question=payload.question,
        options=options or "none given: propose some",
        settled=settled or "none",
        context=payload.context or "none",
    )
