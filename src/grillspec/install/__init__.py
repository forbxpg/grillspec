"""Install grillspec's skills into a harness without a plugin system."""

from __future__ import annotations

from ._install import InstallConflictError, InstallResult, install, uninstall
from ._targets import Scope

__all__ = ("InstallConflictError", "InstallResult", "Scope", "install", "uninstall")
