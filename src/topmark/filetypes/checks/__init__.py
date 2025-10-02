# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/filetypes/checks/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Insert-checker utilities for TopMark file types.

This package provides **file-type specific checks** (``InsertChecker`` instances)
that determine whether a TopMark header can be safely inserted into a given file.

Unlike *content matchers* (see [`topmark.filetypes.detectors`][]), which classify
a file’s type by examining its content, insert checkers focus on **pre-insert
eligibility**. For example, a checker may forbid inserting a header into a JSON
file that is actually JSON without comments, or into an XML document missing a
declaration.

Responsibilities:
    * Expose reusable, file-type specific ``InsertChecker`` callables.
    * Encapsulate constraints that go beyond syntax (e.g., semantic restrictions).
    * Surface advisory reasons when insertion is not supported.

Relationship:
    * [`topmark.filetypes.base`][] defines the ``InsertChecker`` protocol and the
      ``FileType`` dataclass property where these checkers can be attached.
    * [`topmark.filetypes.detectors`][] provides complementary content matchers
      for file type detection.
"""

from __future__ import annotations
