# topmark:header:start
#
#   file         : constants.py
#   file_relpath : src/topmark/constants.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark Constants."""

from importlib.metadata import version as get_version
from pathlib import Path

TOPMARK_VERSION = get_version("topmark")

PYPROJECT_TOML_PATH = Path(__file__).parent.parent / "pyproject.toml"
DEFAULT_TOML_CONFIG_PATH: Path = Path(__file__).parent / "config" / "topmark-default.toml"

TOPMARK_START_MARKER: str = "topmark:header:start"
TOPMARK_END_MARKER: str = "topmark:header:end"

VALUE_NOT_SET: str = "<not set>"
