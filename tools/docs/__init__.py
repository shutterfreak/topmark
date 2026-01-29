# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : tools/docs/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Documentation build helpers for TopMark.

This package contains scripts used during MkDocs builds, including:
- MkDocs simple-hooks (`hooks.py`)
- mkdocs-gen-files generation (`gen_api_pages.py`)
- Shared utility helpers (`docs_utils.py`)

The code here is only imported/executed in documentation tooling contexts (executed by
MkDocs build / mkdocs-gen-files) and is not part of the TopMark runtime library.
"""

from __future__ import annotations
