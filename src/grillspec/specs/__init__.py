"""Specs: parse them and check them against the bundled rules."""

from __future__ import annotations

from ._openspec import openspec_advice
from ._parse import Document, LogItem, Requirement, Scenario, parse_markdown
from ._plan import Plan, PlanTask, parse_plan, valid_test
from ._report import Finding, Report
from ._validate import plan_report, validate_change

__all__ = (
    "Document",
    "Finding",
    "LogItem",
    "Plan",
    "PlanTask",
    "Report",
    "Requirement",
    "Scenario",
    "openspec_advice",
    "parse_markdown",
    "parse_plan",
    "plan_report",
    "valid_test",
    "validate_change",
)
