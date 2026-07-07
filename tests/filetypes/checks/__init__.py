# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : tests/filetypes/checks/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for file type pre-insert checks.

This package contains focused tests for the lightweight pre-insert checkers
used by file type definitions to determine whether header insertion is safe
or should be skipped for policy, content, or idempotence reasons. The tests
exercise the checkers directly, independently of header processors or the
pipeline, to provide stable regression coverage for their public contracts.
"""

from __future__ import annotations
