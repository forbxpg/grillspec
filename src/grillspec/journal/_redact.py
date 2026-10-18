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
_TOKENS = re.compile("|".join(_TOKEN_PATTERNS))
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=\-]{16,}")
_KEY_WORDS = r"(?:password|passwd|pwd|secret|token|api[_\-]?key|access[_\-]?key)"
_PAIRS = re.compile(
    rf"(?i)\b([A-Za-z0-9_]*{_KEY_WORDS}[A-Za-z0-9_]*)(\s*[:=]\s*)([\"']?)[^\s\"']+\3"
)


def redact(text: str) -> str:
    """Remove ``<private>`` spans and replace secrets with ``<redacted>``.

    Args:
        text: str - Text about to be stored.

    Returns:
        str - The text without private spans, keys, tokens or password values.

    """
    text = _PRIVATE.sub("", text)
    text = _PEM.sub(REDACTED, text)
    text = _TOKENS.sub(REDACTED, text)
    text = _BEARER.sub(lambda m: m.group(1) + REDACTED, text)
    return _PAIRS.sub(lambda m: m.group(1) + m.group(2) + REDACTED, text)
