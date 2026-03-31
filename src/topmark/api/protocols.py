# topmark:header:start
#
#   project      : TopMark
#   file         : protocols.py
#   file_relpath : src/topmark/api/protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Stable public structural contracts for TopMark integrations.

This module contains plugin-facing protocols and TypedDict contracts used by
third-party integrations that want to register file types, header processors,
or public policy overlays without importing TopMark's internal base classes.

Use this module for structural contracts. Stable public value types and literal
aliases belong in [`topmark.api.types`][topmark.api.types].

Stability policy:
- Attribute names and types here follow semver.
- Adding new optional attributes is allowed in minor releases.
- Removing/renaming attributes or changing types is a breaking change.

Diagnostics:
- The public API uses JSON-friendly diagnostics with string literal severities.
- See [`DiagnosticEntry`][topmark.api.types.DiagnosticEntry] for the stable
  shape and [`DiagnosticLevelLiteral`][topmark.api.types.DiagnosticLevelLiteral]
  for allowed values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence
    from pathlib import Path


# ---- Plugin-facing structural contracts ----


class PublicFileType(Protocol):
    """Minimal public structural contract for a file type.

    These attributes provide the discovery metadata TopMark needs to recognize
    files and determine whether a header can be managed. Instances are
    registered via the public registry and may be recognized but unsupported
    (`skip_processing`) to enable reporting without modification.

    Required attributes:
        name: Stable identifier (for example, ``"jsonc"``). Must be unique.
        description: Short human description for UI/logs.
        extensions: File extensions (without dot), for example ("json",).
        filenames: Exact file names (for example, ("Makefile",)).
        patterns: Glob-like patterns.
        skip_processing: If `True`, TopMark will not add/update/remove a header
            even if the type matches (still discoverable for reporting).
        header_policy_name: Symbolic policy name used by TopMark to guide
            header placement.

    Optional:
        content_matcher: `Callable[[Path], bool]` that returns `True` only if
            the file contents confirm this specific type. Use this to
            disambiguate overlapping extensions. The callable should be cheap
            and side-effect free; it must not modify files.
    """

    name: str
    description: str
    extensions: Sequence[str]
    filenames: Sequence[str]
    patterns: Sequence[str]
    skip_processing: bool
    content_matcher: Callable[[Path], bool] | None = None
    header_policy_name: str


class PublicHeaderProcessor(Protocol):
    """Minimal public structural contract for a header processor.

    Implementors expose comment delimiters and are attached to a file type
    during registration. At bind time, the registry sets `file_type` on the
    processor instance.

    Required attributes:
        description: Short human description for UI/logs.
        line_prefix: Line comment prefix (if applicable).
        line_suffix: Line comment suffix (if applicable).
        line_indent: Line comment indent (if applicable).
        block_prefix: Block comment prefix (if applicable).
        block_suffix: Block comment suffix (if applicable).
        file_type: The bound
            [`PublicFileType`][topmark.api.protocols.PublicFileType] instance,
            set by the registry.

    Notes:
        A processor represents the behavior for rendering, scanning, and placing
        the TopMark header. It is separate from a file type, which represents
        recognition metadata.
    """

    description: str

    # Line-comment metadata.
    line_prefix: str
    line_suffix: str
    line_indent: str

    # Block-comment metadata.
    block_prefix: str
    block_suffix: str

    # registry binds at runtime
    file_type: PublicFileType
