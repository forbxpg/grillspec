"""Find a member's answer in what its CLI printed."""

from __future__ import annotations

import json
import re
from typing import cast

_FENCE = re.compile(r"```(?:json)?[ \t]*\n(.*?)```", re.DOTALL)


def _contract(value: object) -> dict[str, object] | None:
    """Accept a decoded value that looks like the council contract.

    Args:
        value: object - Decoded JSON.

    Returns:
        dict[str, object] | None - The object when it has a string ``recommend``.

    """
    if not isinstance(value, dict):
        return None
    data = cast("dict[str, object]", value)
    return data if isinstance(data.get("recommend"), str) else None


def extract_contract(text: str) -> dict[str, object] | None:
    """Find the first JSON object with a string ``recommend`` in an answer.

    Tries the whole text, then each fenced block, then every ``{`` in order.

    Args:
        text: str - What the member answered.

    Returns:
        dict[str, object] | None - The contract object; None when there is none.

    """
    for candidate in (text, *_FENCE.findall(text)):
        try:
            found = _contract(cast("object", json.loads(candidate)))
        except ValueError:
            continue
        if found is not None:
            return found
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            value = cast("object", decoder.raw_decode(text, start)[0])
        except ValueError:
            pass
        else:
            found = _contract(value)
            if found is not None:
                return found
        start = text.find("{", start + 1)
    return None
