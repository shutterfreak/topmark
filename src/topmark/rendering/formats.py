# topmark:header:start
#
#   file         : formats.py
#   file_relpath : src/topmark/rendering/formats.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Defines available header rendering formats for the TopMark tool.

This module provides an enumeration of the different formats
that can be used for rendering headers in TopMark.
"""

from enum import Enum


class HeaderOutputFormat(Enum):
    """TopMark header rendering formats."""

    DEFAULT = "default"
    NATIVE = "native"
    PLAIN = "plain"
    JSON = "json"
