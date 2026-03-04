# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/api/commands/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""API command implementations.

This subpackage contains the concrete implementations behind the public façade in
[`topmark.api`][topmark.api].

Import guidance:
- API consumers should prefer importing from `topmark.api` (the curated façade).
- These modules are intentionally small and typed so they can be tested and reused,
  but direct imports from `topmark.api.commands.*` are not the primary contract.
"""

from __future__ import annotations
