"""Read, validate and merge configuration files."""

from __future__ import annotations

import dataclasses
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from ._model import Backend, Config, CouncilMode, Depth

if TYPE_CHECKING:
    from collections.abc import Callable
    from enum import StrEnum

SUPPORTED_VERSION = 1
PROJECT_CONFIG = Path(".grillspec") / "config.toml"


class ConfigError(Exception):
    """A configuration file cannot be used as written."""


@dataclass(frozen=True)
class LoadedConfig:
    """The effective configuration and what was odd about the files.

    Attributes:
        config: Config - Merged configuration.
        warnings: tuple[str, ...] - Non-fatal findings, such as unknown keys.

    """

    config: Config
    warnings: tuple[str, ...]


def _choice(enum: type[StrEnum]) -> Callable[[object, str], object]:
    """Build a parser that accepts one of an enum's values.

    Args:
        enum: type[StrEnum] - The allowed values.

    Returns:
        Callable[[object, str], object] - Parser taking the raw value and its origin.

    """

    def parse(value: object, origin: str) -> object:
        allowed = [member.value for member in enum]
        if value not in allowed:
            msg = f"{origin} is {value!r}; allowed: {', '.join(allowed)}"
            raise ConfigError(msg)
        return enum(value)

    return parse


def _string(value: object, origin: str) -> object:
    """Accept a string.

    Args:
        value: object - Raw value.
        origin: str - Key and file, for the error message.

    Returns:
        object - The value.

    Raises:
        ConfigError: If the value is not a string.

    """
    if not isinstance(value, str):
        msg = f"{origin} must be a string"
        raise ConfigError(msg)
    return value


def _boolean(value: object, origin: str) -> object:
    """Accept a boolean.

    Args:
        value: object - Raw value.
        origin: str - Key and file, for the error message.

    Returns:
        object - The value.

    Raises:
        ConfigError: If the value is not a boolean.

    """
    if not isinstance(value, bool):
        msg = f"{origin} must be true or false"
        raise ConfigError(msg)
    return value


def _strings(value: object, origin: str) -> object:
    """Accept a list of strings.

    Args:
        value: object - Raw value.
        origin: str - Key and file, for the error message.

    Returns:
        object - The value as a tuple.

    Raises:
        ConfigError: If the value is not a list of strings.

    """
    items = cast("list[object]", value) if isinstance(value, list) else None
    if items is None or not all(isinstance(item, str) for item in items):
        msg = f"{origin} must be a list of strings"
        raise ConfigError(msg)
    return tuple(cast("list[str]", items))


# Dotted key -> (Config field, parser).
_SCHEMA: dict[str, tuple[str, Callable[[object, str], object]]] = {
    "spec.backend": ("backend", _choice(Backend)),
    "spec.artifacts_language": ("artifacts_language", _string),
    "grill.depth": ("depth", _choice(Depth)),
    "council.enabled": ("council_enabled", _choice(CouncilMode)),
    "council.members": ("council_members", _strings),
    "gates.enabled": ("gates_enabled", _boolean),
}


def user_config_path() -> Path:
    r"""Return where the user-level configuration lives on this system.

    Returns:
        Path - ``$XDG_CONFIG_HOME/grillspec/config.toml`` when set, else
            ``%APPDATA%\\grillspec\\config.toml`` on Windows, else
            ``~/.config/grillspec/config.toml``.

    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "grillspec" / "config.toml"
    appdata = os.environ.get("APPDATA")
    if sys.platform == "win32" and appdata:
        return Path(appdata) / "grillspec" / "config.toml"
    return Path.home() / ".config" / "grillspec" / "config.toml"


def _read(path: Path) -> tuple[dict[str, object], list[str]]:
    """Read one configuration file into validated field values.

    Args:
        path: Path - The file; a missing file yields no values.

    Returns:
        tuple[dict[str, object], list[str]] - Config field values and warnings.

    Raises:
        ConfigError: If the file is malformed or holds an invalid value.

    """
    if not path.is_file():
        return {}, []
    try:
        data: dict[str, object] = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        msg = f"{path}: invalid TOML: {error}"
        raise ConfigError(msg) from error
    except OSError as error:
        msg = f"{path}: unreadable: {error}"
        raise ConfigError(msg) from error
    version = data.pop("version", SUPPORTED_VERSION)
    if type(version) is not int or version != SUPPORTED_VERSION:
        msg = f"{path}: unsupported version {version!r}; this grillspec reads 1"
        raise ConfigError(msg)
    values: dict[str, object] = {}
    warnings: list[str] = []
    for section, table in data.items():
        if not isinstance(table, dict):
            warnings.append(f"{path}: unknown key {section!r} ignored")
            continue
        for name, raw in cast("dict[str, object]", table).items():
            key = f"{section}.{name}"
            if key not in _SCHEMA:
                warnings.append(f"{path}: unknown key {key!r} ignored")
                continue
            field, parse = _SCHEMA[key]
            values[field] = parse(raw, f"{key} in {path}")
    return values, warnings


def load_config(project_root: Path, *, user_path: Path | None = None) -> LoadedConfig:
    """Load the effective configuration for a project.

    Args:
        project_root: Path - Root of the project (holds ``.grillspec/``).
        user_path: Path | None - User configuration file; the platform default
            when None.

    Returns:
        LoadedConfig - Project values over user values over defaults, per key.

    """
    user_values, user_warnings = _read(user_path or user_config_path())
    project_values, project_warnings = _read(project_root / PROJECT_CONFIG)
    config = dataclasses.replace(Config(), **{**user_values, **project_values})
    return LoadedConfig(config, tuple(user_warnings + project_warnings))
