# topmark:header:start
#
#   project      : TopMark
#   file         : io.py
#   file_relpath : src/topmark/config/io.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Lightweight I/O helpers for TopMark configuration.

This module centralizes small, **pure** functions used by the configuration
layer to read/write TOML content. Keeping these helpers in a separate module
ensures a clean separation of concerns:

- `topmark.config.__init__` contains only data models and merge logic
  (``MutableConfig`` builder and frozen ``Config`` snapshot).
- This module contains small utilities to *load* packaged defaults, *load*
  external TOML files, and *normalize* TOML text without retaining comments.

These functions are deliberately side-effect free and do not mutate the
configuration models. They can be unit-tested in isolation.
"""

from __future__ import annotations

from importlib.resources import files
from typing import TYPE_CHECKING, Any

import toml

from topmark.config.logging import get_logger
from topmark.constants import DEFAULT_TOML_CONFIG_RESOURCE

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


def load_defaults_dict() -> dict[str, Any]:
    """Return the packaged default configuration as a Python dict.

    The default TOML is shipped as a package resource (see
    `DEFAULT_TOML_CONFIG_RESOURCE`). This function reads the resource
    and parses it into a dictionary using ``toml``.

    Returns:
        dict[str, Any]: The parsed default configuration.
    """
    res = files("topmark.config") / DEFAULT_TOML_CONFIG_RESOURCE
    logger.debug("Loading defaults from package resource: %s", res)

    return toml.loads(res.read_text(encoding="utf-8"))


def load_toml_dict(path: "Path") -> dict[str, Any]:
    """Load and parse a TOML file from the filesystem.

    Args:
        path (Path): Path to a TOML document (e.g., ``topmark.toml`` or
            ``pyproject.toml``).

    Returns:
        dict[str, Any]: The parsed TOML content.
    """
    return toml.load(path)


def clean_toml(text: str) -> str:
    """Normalize a TOML document, removing comments and formatting noise.

    This is useful for presenting a canonicalized view of a TOML document,
    for example in ``topmark dump-config`` outputs or for snapshotting.

    Args:
        text (str): Raw TOML content.

    Returns:
        str: A normalized TOML string produced by round-tripping through the
            TOML parser and dumper.
    """
    # Parse the default config TOML and re-dump it to normalize formatting
    return toml.dumps(toml.loads(text))


def to_toml(toml_dict: dict[str, Any]) -> str:
    """Return the TOML document for the given TOML dict.

    Args:
        toml_dict (dict[str, Any]): the TOML dict to be rendered into TOML.

    Returns:
        str: The resulting rendered TOML document.
    """
    return toml.dumps(toml_dict)
