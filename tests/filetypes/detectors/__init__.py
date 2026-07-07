# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : tests/filetypes/detectors/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for file type content detectors.

This package contains focused tests for detector helpers that classify file
content during file type resolution. The tests validate detector contracts in
isolation from registry, resolution, and processor behavior so that
classification heuristics can evolve without weakening their externally
observable guarantees.
"""

from __future__ import annotations
