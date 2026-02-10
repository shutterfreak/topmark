# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/cli_shared/emitters/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared CLI emitters.

This package contains output-format-specific emitters and shared preparation helpers
for TopMark's command-line interface.

The intent is to keep `cli/commands/*` as orchestration only:

- *Preparation* of reusable, human-facing payloads lives in `cli_shared/emitters/shared`.
- *Rendering* for specific formats lives in subpackages like `cli_shared/emitters/markdown`.

Notes:
    - ANSI-styled (default) emitters live under [`topmark.cli.emitters`][topmark.cli.emitters].
    - Machine formats (JSON/NDJSON) are implemented via `topmark.*.machine` serializers and routed
      through [`topmark.cli.machine_emitters`][topmark.cli.machine_emitters].
"""

from __future__ import annotations
