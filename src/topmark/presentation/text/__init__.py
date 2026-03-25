# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/presentation/text/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Text, optionally ANSI-styled CLI renderers (default).

The default output format is intended for interactive terminal use and may apply color/styling
through the console abstraction. These helpers do not perform I/O.

Command implementations should delegate formatting to renderers in this package after preparing any
shared data via [`topmark.presentation.shared`][topmark.presentation.shared].
"""

from __future__ import annotations
