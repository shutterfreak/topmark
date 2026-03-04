# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/version/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark version domain helpers.

This package provides a small, typed surface for working with TopMark's version
string at runtime, including optional conversion from the subset of PEP 440 that
TopMark emits to a SemVer-ish representation.

Public surface:
- `compute_version_info`: build a `VersionInfo` payload (optionally SemVer)
- `convert_pep440_to_semver`: conversion helper used by `compute_version_info`
- `VersionInfo`, `VersionFormatLiteral`: payload + types
"""

from __future__ import annotations
