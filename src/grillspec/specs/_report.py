"""What the validator found."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    """One problem in a spec.

    Attributes:
        severity: str - ``error`` (blocks approval) or ``warning``.
        path: Path - File, relative to the project root.
        line: int - 1-based line; 0 when the finding is about the whole file.
        rule: str - Rule name, such as ``scenario-id``.
        message: str - What is wrong and how to fix it.

    """

    severity: str
    path: Path
    line: int
    rule: str
    message: str

    def text(self) -> str:
        """Render the finding as one line.

        Returns:
            str - ``<severity> <path>:<line> <rule>: <message>``.

        """
        where = f"{self.path.as_posix()}:{self.line}"
        return f"{self.severity} {where} {self.rule}: {self.message}"

    def to_json(self) -> dict[str, object]:
        """Return the finding as a JSON-ready object.

        Returns:
            dict[str, object] - The fields by name.

        """
        return {
            "severity": self.severity,
            "path": self.path.as_posix(),
            "line": self.line,
            "rule": self.rule,
            "message": self.message,
        }


@dataclass(frozen=True)
class Report:
    """Everything the validator found in one change.

    Attributes:
        change: str - Change id.
        errors: tuple[Finding, ...] - Findings that block approval.
        warnings: tuple[Finding, ...] - Findings that do not.

    """

    change: str
    errors: tuple[Finding, ...]
    warnings: tuple[Finding, ...]

    def to_json(self) -> dict[str, object]:
        """Return the report as a JSON-ready object.

        Returns:
            dict[str, object] - ``{version: 1, change, errors, warnings}``.

        """
        return {
            "version": 1,
            "change": self.change,
            "errors": [finding.to_json() for finding in self.errors],
            "warnings": [finding.to_json() for finding in self.warnings],
        }
