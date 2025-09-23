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

TOPMARK_VERSION: str = get_version("topmark")

PYPROJECT_TOML_PATH: Path = Path(__file__).parent.parent.parent / "pyproject.toml"

# Name of the bundled default config inside the package `topmark.config`.
# This is used with importlib.resources in config/__init__.py
DEFAULT_TOML_CONFIG_RESOURCE: str = "topmark-default.toml"

TOPMARK_START_MARKER: str = "topmark:header:start"
TOPMARK_END_MARKER: str = "topmark:header:end"

VALUE_NOT_SET: str = "<not set>"
