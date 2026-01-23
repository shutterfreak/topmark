# topmark:header:start
#
#   project      : TopMark
#   file         : constants.py
#   file_relpath : src/topmark/constants.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark Constants."""

from __future__ import annotations

from importlib.metadata import version as get_version
from pathlib import Path
from typing import Final

TOPMARK_VERSION: Final[str] = get_version("topmark")

PYPROJECT_TOML_PATH: Path = Path(__file__).parent.parent.parent / "pyproject.toml"

# Name of the bundled default config inside the package `topmark.config`:
DEFAULT_TOML_CONFIG_PACKAGE: Final[str] = "topmark.config"
DEFAULT_TOML_CONFIG_NAME: Final[str] = "topmark-default.toml"

TOPMARK_START_MARKER: Final[str] = "topmark:header:start"
TOPMARK_END_MARKER: Final[str] = "topmark:header:end"

TOML_BLOCK_START: Final[str] = "# === BEGIN[TOML] ==="
TOML_BLOCK_END: Final[str] = "# === END[TOML] ==="

VALUE_NOT_SET: Final[str] = "<not set>"


CLI_OVERRIDE_STR: Final[str] = "<CLI overrides>"
