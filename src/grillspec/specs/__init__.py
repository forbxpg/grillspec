"""Specs: parse them and check them against the bundled rules."""

from __future__ import annotations

from ._openspec import openspec_advice
from ._parse import Document, LogItem, Requirement, Scenario, parse_markdown
from ._report import Finding, Report
from ._validate import validate_change

__all__ = (
    "Document",
    "Finding",
    "LogItem",
    "Report",
    "Requirement",
    "Scenario",
    "openspec_advice",
    "parse_markdown",
    "validate_change",
)
