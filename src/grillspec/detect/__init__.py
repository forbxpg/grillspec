"""What is around: brownfield signals and agent CLIs on PATH."""

from __future__ import annotations

from ._detect import (
    CliStatus,
    Signals,
    available_clis,
    brownfield_signals,
    cli_report,
    council_defaults,
    recommend_backend,
)

__all__ = (
    "CliStatus",
    "Signals",
    "available_clis",
    "brownfield_signals",
    "cli_report",
    "council_defaults",
    "recommend_backend",
)
