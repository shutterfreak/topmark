# topmark:header:start
#
#   project      : TopMark
#   file         : protocols.py
#   file_relpath : src/topmark/api/protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Plugin-facing structural contracts for TopMark integrations.

This module contains protocols used by integrations that want to register file
types or header processors without importing TopMark's internal base classes.

Use this module for structural contracts. Stable public value types and literal
aliases belong in [`topmark.api.types`][topmark.api.types]. Symbols exported by
[`topmark.api`][topmark.api] are governed by the public API snapshot; this
module is public-adjacent integration surface, but is not re-exported from the
facade package.

Compatibility policy:
- Attribute names and types should remain stable unless a pre-1.0 cleanup or a
  concrete integration bug requires changing them.
- Adding optional attributes is preferred over broad protocol reshaping.
- Removing/renaming attributes or changing types should be treated as an
  integration-facing breaking change even when the public API snapshot is
  unchanged.
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
    """Minimal plugin-facing structural contract for a file type.

    These attributes provide the discovery metadata TopMark needs to recognize
    files and determine whether a header can be managed. Instances are
    registered via the public registry and may be recognized but unsupported
    (`skip_processing`) to enable reporting without modification.

    Attributes:
        name: Stable identifier (for example, ``"jsonc"``). Must be unique.
        description: Short human description for UI/logs.
        extensions: File extensions (without dot), for example ("json",).
        filenames: Exact file names (for example, ("Makefile",)).
        patterns: Glob-like patterns.
        skip_processing: If `True`, TopMark will not add/update/remove a header
            even if the type matches (still discoverable for reporting).
        content_matcher: Optional `Callable[[Path], bool]` that returns `True`
            only if the file contents confirm this specific type. Use this to
            disambiguate overlapping extensions. The callable should be cheap
            and side-effect free; it must not modify files.
        header_policy_name: Symbolic policy name used by TopMark to guide
            header placement.
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
    """Minimal plugin-facing structural contract for a header processor.

    Implementors expose comment delimiters and are attached to a file type
    during registration. At bind time, the registry sets `file_type` on the
    processor instance.

    Attributes:
        description: Short human description for UI/logs.
        line_prefix: Line comment prefix (if applicable).
        line_suffix: Line comment suffix (if applicable).
        line_indent: Line comment indent (if applicable).
        block_prefix: Block comment prefix (if applicable).
        block_suffix: Block comment suffix (if applicable).
        file_type: The bound
            [`PublicFileType`][topmark.api.protocols.PublicFileType] instance.
            The registry assigns this attribute at bind time, so it intentionally
            remains mutable instance state.

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

    # The registry assigns this mutable binding at runtime.
    file_type: PublicFileType
