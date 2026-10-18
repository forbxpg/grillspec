"""Strip private spans and secrets from text before it is stored."""

from __future__ import annotations

import re

REDACTED = "<redacted>"
_PRIVATE = re.compile(r"<private>.*?(?:</private>|\Z)", re.IGNORECASE | re.DOTALL)
_PEM = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)",
    re.DOTALL,
)
_TOKEN_PATTERNS = (
    r"sk-[A-Za-z0-9_\-]{8,}",
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"xox[abpr]-[A-Za-z0-9\-]{10,}",
    r"AKIA[0-9A-Z]{16}",
    r"glpat-[A-Za-z0-9_\-]{20,}",
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",
)
# A token starts a word: "task-dependencies" holds no "sk-" key.
_TOKENS = re.compile(r"(?<![A-Za-z0-9_\-])(?:" + "|".join(_TOKEN_PATTERNS) + ")")
_URL_CREDS = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://[^\s:/@]+:)[^\s@/]+(@)")
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=\-]{16,}")
_BASIC = re.compile(r"\b(Basic\s+)([A-Za-z0-9+/]{8,}={0,2})(?![A-Za-z0-9+/=])")
# Words whose value is a secret whatever it looks like.
_ALWAYS = r"password|passwd|pwd|пароль"
# Words that also name settings in prose ("max_tokens=4096", "token: the cap").
_MAYBE = r"secret|token|api[_\-]?key|access[_\-]?key|секрет|токен|ключ"
_VALUE = r"(\"[^\"\n]*\"|'[^'\n]*'|[^\s,;\"'}\]]+)"
_KEY = rf"([\w\-]*?(?:({_ALWAYS})|{_MAYBE})[\w\-]*)"
_PAIRS = re.compile(rf"(?i)(?<![\w\-])([\"']?){_KEY}\1(\s*[:=]\s*){_VALUE}")
_LETTER = re.compile(r"[^\W\d_]")
_DIGIT = re.compile(r"\d")
_LONG = 16


def _secret_value(value: str) -> bool:
    """Tell whether a setting's value looks like a secret rather than prose.

    Args:
        value: str - The value as written, quotes included.

    Returns:
        bool - True for a quoted value, a mix of letters and digits, or a long one.

    """
    if value[:1] in {'"', "'"}:
        return True
    mixed = bool(_LETTER.search(value)) and bool(_DIGIT.search(value))
    return mixed or len(value) >= _LONG


def _pair(match: re.Match[str]) -> str:
    quote, key, always, sep, value = match.groups()
    if not always and not _secret_value(value):
        return match.group(0)
    wrapped = value[0] + REDACTED + value[0] if value[:1] in {'"', "'"} else REDACTED
    return f"{quote}{key}{quote}{sep}{wrapped}"


def _basic(match: re.Match[str]) -> str:
    prefix, value = match.groups()
    if not re.search(r"[\d+/=]", value):
        return match.group(0)  # "Basic understanding", not credentials
    return prefix + REDACTED


def redact(text: str) -> str:
    """Remove ``<private>`` spans and replace secrets with ``<redacted>``.

    Args:
        text: str - Text about to be stored.

    Returns:
        str - The text without private spans, keys, tokens or password values.

    """
    text = _PRIVATE.sub("", text)
    text = _PEM.sub(REDACTED, text)
    text = _URL_CREDS.sub(lambda m: m.group(1) + REDACTED + m.group(2), text)
    text = _TOKENS.sub(REDACTED, text)
    text = _BEARER.sub(lambda m: m.group(1) + REDACTED, text)
    text = _BASIC.sub(_basic, text)
    return _PAIRS.sub(_pair, text)
