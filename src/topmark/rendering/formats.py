# topmark:header:start
#
#   project      : TopMark
#   file         : formats.py
#   file_relpath : src/topmark/rendering/formats.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Defines available header rendering formats for the TopMark tool.

This module provides an enumeration of the different formats
that can be used for rendering headers in TopMark.
"""

from __future__ import annotations

from enum import Enum


class HeaderOutputFormat(Enum):
    """TopMark header rendering formats."""

    DEFAULT = "default"
    NATIVE = "native"
    PLAIN = "plain"
    JSON = "json"
