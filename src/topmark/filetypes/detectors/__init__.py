# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/filetypes/detectors/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Content-based file type detectors.

This package hosts lightweight, side-effect-free probes that inspect file
content to disambiguate formats that share extensions (e.g., JSON vs JSONC).

Typical usage is to reference detector callables from a ``FileType`` via a
``content_matcher`` and restrict invocation with a ``content_gate`` (e.g.,
``IF_EXTENSION``) to keep detection fast.

Submodules:
    jsonc: Heuristic JSON-with-comments detection.

Notes:
    Detectors should be fast and read only a small prefix of the file. Avoid
    importing heavy dependencies here to keep CLI startup time low.
"""

from __future__ import annotations
