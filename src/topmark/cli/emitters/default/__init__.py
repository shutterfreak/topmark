# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/cli/emitters/default/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""ANSI-styled (default) CLI emitters.

The default output format is intended for interactive terminal use and may apply color/styling
through the console abstraction.

Command implementations should delegate formatting to emitters in this package after preparing any
shared data via [`topmark.cli_shared.emitters.shared`][topmark.cli_shared.emitters.shared].
"""

from __future__ import annotations
