# topmark:header:start
#
#   project      : TopMark
#   file         : formats.py
#   file_relpath : src/topmark/rendering/formats.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header rendering formats for TopMark.

This module defines `HeaderOutputFormat`, which controls how rendered headers are serialized
(native comment style, plain text, JSON, etc.).
"""

from __future__ import annotations

from enum import Enum


class HeaderOutputFormat(Enum):
    """TopMark header rendering formats."""

    DEFAULT = "default"
    NATIVE = "native"
    PLAIN = "plain"
    JSON = "json"
