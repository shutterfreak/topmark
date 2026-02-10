# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/cli_shared/emitters/markdown/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown CLI emitters.

Emitters in this package render human-facing output as Markdown.

Most emitters consume prepared payloads produced by helpers in
[`topmark.cli_shared.emitters.shared`][topmark.cli_shared.emitters.shared] to keep command
implementations DRY and to ensure consistent output across human formats.
"""

from __future__ import annotations
