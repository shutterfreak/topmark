# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/presentation/markdown/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown CLI emitters.

Renderers in this package render human-facing output as Markdown. These helpers do not perform I/O.

Command implementations should delegate formatting to renderers in this package after preparing any
shared data via [`topmark.presentation.shared`][topmark.presentation.shared].
"""

from __future__ import annotations
