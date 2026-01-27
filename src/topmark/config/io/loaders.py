# topmark:header:start
#
#   project      : TopMark
#   file         : loaders.py
#   file_relpath : src/topmark/config/io/loaders.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Load TOML configuration sources.

This module provides I/O helpers for reading TopMark configuration from:
- the packaged default TOML resource, and
- on-disk TOML files (`topmark.toml` / `pyproject.toml`).

Parsing is done with `tomlkit` and returned as plain `dict` structures.
"""

from __future__ import annotations

from importlib.resources import files
from typing import TYPE_CHECKING, Any, cast

import tomlkit
from tomlkit.exceptions import ParseError as TomlkitParseError

from topmark.config.logging import get_logger
from topmark.constants import DEFAULT_TOML_CONFIG_NAME, DEFAULT_TOML_CONFIG_PACKAGE

if TYPE_CHECKING:
    import sys

    if sys.version_info < (3, 14):
        # Python <=3.13
        from importlib.abc import Traversable
    else:
        # Python 3.14+: Traversable moved here
        from importlib.resources.abc import Traversable
    from pathlib import Path

    from topmark.config.logging import TopmarkLogger

    from .types import TomlTable

logger: TopmarkLogger = get_logger(__name__)

# --- TOML file I/O and normalization ---


def load_defaults_dict() -> TomlTable:
    """Return the packaged default configuration as a Python dict.

    Reads the bundled TOML resource from the ``topmark.config`` package using
    ``importlib.resources.files`` and parses it into a dictionary.

    Returns:
        TomlTable: The parsed default configuration.

    Raises:
        RuntimeError: If the bundled default config resource cannot be read or
            parsed as TOML.
        TypeError: If the bundled default config did not parse to a TOML table.
    """
    resource: Traversable = files(DEFAULT_TOML_CONFIG_PACKAGE).joinpath(DEFAULT_TOML_CONFIG_NAME)
    logger.debug("Loading defaults from package resource: %s", resource)
    try:
        text: str = resource.read_text(encoding="utf8")
    except OSError as exc:
        raise RuntimeError(
            f"Cannot read bundled default config {DEFAULT_TOML_CONFIG_PACKAGE!r}/"
            f"{DEFAULT_TOML_CONFIG_NAME!r}: {exc}"
        ) from exc

    try:
        doc: tomlkit.TOMLDocument = tomlkit.parse(text)
        data_any: Any = doc.unwrap()
        if not isinstance(data_any, dict):
            raise TypeError(
                f"Bundled default config {DEFAULT_TOML_CONFIG_PACKAGE!r}/"
                f"{DEFAULT_TOML_CONFIG_NAME!r} did not parse to a table."
            )
        return cast("TomlTable", data_any)
    except TomlkitParseError as exc:
        raise RuntimeError(
            f"Bundled default config {DEFAULT_TOML_CONFIG_PACKAGE!r}/"
            f"{DEFAULT_TOML_CONFIG_NAME!r} is invalid TOML: {exc}"
        ) from exc


def load_toml_dict(path: Path) -> TomlTable:
    """Load and parse a TOML file from the filesystem.

    Args:
        path (Path): Path to a TOML document (e.g., ``topmark.toml`` or
            ``pyproject.toml``).

    Returns:
        TomlTable: The parsed TOML content.

    Notes:
        - Errors are logged and an empty dict is returned on failure.
        - Encoding is assumed to be UTF-8.
    """
    try:
        text: str = path.read_text(encoding="utf-8")
        doc: tomlkit.TOMLDocument = tomlkit.parse(text)
        data_any: Any = doc.unwrap()
        return cast("TomlTable", data_any) if isinstance(data_any, dict) else {}
    except OSError as e:
        logger.error("Error loading TOML from %s: %s", path, e)
        return {}
    except TomlkitParseError as e:
        logger.error("Error decoding TOML from %s: %s", path, e)
        return {}
    except (TypeError, ValueError) as e:
        logger.error("Unknown error while reading TOML from %s: %s", path, e)
        return {}
