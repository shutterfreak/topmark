# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/resolution/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Input, file type, and processor resolution utilities.

The [`topmark.resolution`][topmark.resolution] package contains helpers that
answer two related runtime questions:

- which filesystem paths TopMark should process;
- which [`FileType`][topmark.filetypes.model.FileType] and bound
  [`HeaderProcessor`][topmark.processors.base.HeaderProcessor] apply to each
  resolved file.

Conceptually, this package sits between the registry and the pipeline:

- **Registry layer** ([`topmark.registry`][topmark.registry])
  Maintains the composed registries of file types and header processors.
- **Resolution layer** ([`topmark.resolution`][topmark.resolution])
  Resolves concrete inputs, file types, and processor bindings.
- **Pipeline layer** ([`topmark.pipeline`][topmark.pipeline])
  Orchestrates processing steps and updates the processing context.

The resolution logic is intentionally separated from the pipeline so it can be
reused independently by tooling, tests, and future APIs.

Current module roles:

- [`topmark.resolution.files`][topmark.resolution.files] decides **which files**
  should be processed by expanding configured inputs and applying path-based and
  file-type-based filters.
- [`topmark.resolution.filetypes`][topmark.resolution.filetypes] decides **what
  each file is** by scoring matching file type candidates and resolving the
  associated processor binding.

Typical entry points include:

- `resolve_file_list()` - determine the concrete input files to process.
- `resolve_file_type_for_path()` - determine the best matching file type for a path.
- `resolve_binding_for_path()` - resolve both file type and processor for a path.
- `get_file_type_candidates_for_path()` - inspect all candidate file type matches and their scores.

These helpers respect optional include/exclude file type filters, allowing
callers to constrain resolution when required.
"""

from __future__ import annotations
