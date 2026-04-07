# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/toml/machine/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output helpers for TOML provenance exports.

This package contains the TOML-domain machine-output components used to expose
resolved TopMark TOML provenance in a stable, machine-readable form.

Responsibilities:
  - Define TOML provenance payload schemas.
  - Build JSON-friendly payload objects from resolved TOML sources.

This package does not define shared envelope primitives; those remain in
[`topmark.core.machine`][topmark.core.machine].
"""

from __future__ import annotations
