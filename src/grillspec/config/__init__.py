"""Layered grillspec configuration: project over user over built-in defaults."""

from __future__ import annotations

from ._load import ConfigError, LoadedConfig, load_config, user_config_path
from ._model import (
    ROLE_NAMES,
    VENDOR_NAMES,
    Backend,
    Config,
    CouncilMode,
    Depth,
    External,
    Member,
    parse_member,
)

__all__ = (
    "ROLE_NAMES",
    "VENDOR_NAMES",
    "Backend",
    "Config",
    "ConfigError",
    "CouncilMode",
    "Depth",
    "External",
    "LoadedConfig",
    "Member",
    "load_config",
    "parse_member",
    "user_config_path",
)
