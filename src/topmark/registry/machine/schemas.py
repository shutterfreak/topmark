# topmark:header:start
#
#   project      : TopMark
#   file         : schemas.py
#   file_relpath : src/topmark/registry/machine/schemas.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Registry machine-output schema types.

This module defines the *typing surface* for machine-readable output emitted by
registry-related commands (currently `topmark filetypes` and `topmark processors`).

These are schema-only types:
- They describe the JSON/NDJSON payload shapes.
- They help keep payload builders and shape builders consistent.
- They do not perform serialization or printing.

Why `TypedDict`:
- Registry payloads are composed from runtime objects and emitted as plain
  dict/list structures.
- The payloads are small, shallow, and naturally expressed as JSON objects.

Serialization conventions:
- JSON mode wraps a payload in a top-level envelope with `meta` plus a stable key.
- NDJSON mode emits one record per entity, using the canonical record envelope
  (`kind` + `meta` + payload container).

Payload construction lives in
[`topmark.registry.machine.payloads`][topmark.registry.machine.payloads].
Envelope/record shaping lives in
[`topmark.registry.machine.shapes`][topmark.registry.machine.shapes].
"""

from __future__ import annotations

from typing import TypedDict


class FileTypeBriefEntry(TypedDict):
    """Brief file type entry used when `--show-details` is not requested."""

    name: str
    description: str


class FileTypeDetailEntry(TypedDict):
    """Detailed file type entry used when `--show-details` is enabled."""

    name: str
    description: str
    extensions: list[str]
    filenames: list[str]
    patterns: list[str]
    skip_processing: bool
    has_content_matcher: bool
    has_insert_checker: bool
    header_policy: str


FileTypeEntry = FileTypeBriefEntry | FileTypeDetailEntry
"""Single file type entry (brief or detailed)."""

FileTypesPayload = list[FileTypeEntry]
"""Payload for `topmark filetypes`: a list of entries sorted by file type key."""


class FileTypeRefEntry(TypedDict):
    """Expanded file type reference used inside processor detail entries."""

    name: str
    description: str


FileTypeRef = str | FileTypeRefEntry
"""Reference to a file type.

- In brief mode: a string containing the file type name.
- In detail mode: an object containing `name` and `description`.
"""


class ProcessorBriefEntry(TypedDict):
    """Brief header-processor entry.

    In brief mode, `filetypes` is a list of file type names.
    """

    module: str
    class_name: str
    filetypes: list[str]


class ProcessorDetailEntry(TypedDict):
    """Detailed header-processor entry.

    In detail mode, `filetypes` is a list of expanded file type references.
    """

    module: str
    class_name: str
    filetypes: list[FileTypeRefEntry]


ProcessorEntry = ProcessorBriefEntry | ProcessorDetailEntry
"""Single processor entry (brief or detailed)."""


class ProcessorsPayload(TypedDict):
    """Payload for `topmark processors`.

    Attributes:
        processors: One entry per concrete header processor class, with associated file types.
        unbound_filetypes: File types that have no registered header processor.
    """

    processors: list[ProcessorEntry]
    unbound_filetypes: list[FileTypeRef]
