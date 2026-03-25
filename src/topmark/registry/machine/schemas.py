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
registry-related commands (currently `topmark registry filetypes`, `topmark registry processors`
and `topmark registry bindings`).

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
[`topmark.registry.machine.envelopes`][topmark.registry.machine.envelopes].
"""

from __future__ import annotations

from typing import TypeAlias
from typing import TypedDict


class FileTypePolicyEntry(TypedDict):
    """Structured file type policy entry for machine output.

    This mirrors the public API policy shape and keeps machine output stable and
    self-describing.
    """

    supports_shebang: bool
    encoding_line_regex: str | None
    pre_header_blank_after_block: int
    ensure_blank_after_header: bool
    blank_collapse_mode: str
    blank_collapse_extra: str


class FileTypeBriefEntry(TypedDict):
    """Brief file type entry used when `--show-details` is not requested."""

    local_key: str
    namespace: str
    qualified_key: str
    description: str


class FileTypeDetailEntry(TypedDict):
    """Detailed file type entry used when `--show-details` is enabled."""

    local_key: str
    namespace: str
    qualified_key: str
    description: str

    bound: bool
    extensions: list[str]
    filenames: list[str]
    patterns: list[str]
    skip_processing: bool
    has_content_matcher: bool
    has_insert_checker: bool
    policy: FileTypePolicyEntry


FileTypeEntry: TypeAlias = FileTypeBriefEntry | FileTypeDetailEntry
"""Single file type entry (brief or detailed)."""

FileTypesPayload: TypeAlias = list[FileTypeEntry]
"""Payload for `topmark registry filetypes`: a list of entries sorted by file type key."""


class FileTypeRefEntry(TypedDict):
    """Expanded file type reference used in auxiliary registry listings."""

    local_key: str
    namespace: str
    qualified_key: str
    description: str


FileTypeRef: TypeAlias = str | FileTypeRefEntry
"""Reference to a file type.

- In brief mode: a string containing the qualified file type identifier.
- In detail mode: an object containing identity and description fields.
"""


class ProcessorBriefEntry(TypedDict):
    """Brief header-processor entry used when `--show-details` is not requested."""

    local_key: str
    namespace: str
    qualified_key: str
    description: str


class ProcessorDetailEntry(TypedDict):
    """Detailed header-processor entry used when `--show-details` is enabled."""

    local_key: str
    namespace: str
    qualified_key: str
    description: str
    bound: bool
    line_indent: str
    line_prefix: str
    line_suffix: str
    block_prefix: str
    block_suffix: str


ProcessorEntry: TypeAlias = ProcessorBriefEntry | ProcessorDetailEntry
"""Single processor entry (brief or detailed)."""


class ProcessorsPayload(TypedDict):
    """Payload for `topmark registry processors`.

    This payload is now identity-focused: it lists registered processors rather
    than grouping file types under each processor.
    """

    processors: list[ProcessorEntry]


class BindingBriefEntry(TypedDict):
    """Brief binding entry used when `--show-details` is not requested."""

    file_type_key: str
    processor_key: str


class BindingDetailEntry(TypedDict):
    """Detailed binding entry used when `--show-details` is enabled."""

    file_type_key: str
    file_type_local_key: str
    file_type_namespace: str
    processor_key: str
    processor_local_key: str
    processor_namespace: str
    file_type_description: str
    processor_description: str


BindingEntry: TypeAlias = BindingBriefEntry | BindingDetailEntry
"""Single binding entry (brief or detailed)."""


class ProcessorRefEntry(TypedDict):
    """Expanded processor reference used for unused processor listings."""

    local_key: str
    namespace: str
    qualified_key: str
    description: str


ProcessorRef: TypeAlias = str | ProcessorRefEntry
"""Reference to a processor.

- In brief mode: a string containing the qualified processor identifier.
- In detail mode: an object containing identity and description fields.
"""


class BindingsPayload(TypedDict):
    """Payload for `topmark registry bindings`.

    Attributes:
        bindings: Effective file-type-to-processor bindings.
        unbound_filetypes: File types that have no effective processor binding.
        unused_processors: Registered processors that do not currently participate
            in an effective binding.
    """

    bindings: list[BindingEntry]
    unbound_filetypes: list[FileTypeRef]
    unused_processors: list[ProcessorRef]
