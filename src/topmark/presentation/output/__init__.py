# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/presentation/output/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Output-level presentation facades for human formats.

This package contains orchestration helpers that combine human-format-specific
renderers into command-level output payloads. The modules here sit above the
TEXT and Markdown renderers and keep stream-routing decisions out of both CLI
commands and low-level renderer modules.
"""

from __future__ import annotations
