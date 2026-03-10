# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/resolution/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""File type and processor resolution utilities.

The [`topmark.resolution`][topmark.resolution] package contains helpers that resolve files
on disk to TopMark *file types* and their associated *header processors*.

This layer implements the runtime resolution logic used by the pipeline.
It evaluates candidate [`topmark.filetypes.model.FileType`][topmark.filetypes.model.FileType]
instances against a file path (and optionally file content), scores matching
candidates, and selects the most appropriate one. Once a file type has been
determined, the corresponding
[`topmark.processors.base.HeaderProcessor`][topmark.processors.base.HeaderProcessor] is retrieved
from the registry.

Conceptually, this package sits between the registry and the pipeline:

- **Registry layer** ([`topmark.registry`][topmark.registry])
  Maintains the registries of file types and header processors.

- **Resolution layer** ([`topmark.resolution`][topmark.resolution])
  Determines which file type and processor apply to a given file.

- **Pipeline layer** ([`topmark.pipeline`][topmark.pipeline])
  Orchestrates processing steps and updates the processing context.

The resolution logic is intentionally separated from the pipeline so that
file type detection and processor selection can be reused independently,
for example by tooling, tests, or future APIs.

Typical entry points include:

- `resolve_file_type_for_path` - determine the best matching file type for a path.
- `resolve_binding_for_path` - resolve both file type and processor for a path.
- `get_file_type_candidates_for_path` - inspect all candidate matches and their scores.

These helpers respect optional include/exclude filters for file types,
allowing callers to constrain resolution when required.
"""

from __future__ import annotations
