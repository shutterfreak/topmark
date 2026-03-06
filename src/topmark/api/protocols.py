# topmark:header:start
#
#   project      : TopMark
#   file         : protocols.py
#   file_relpath : src/topmark/api/protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public protocols for TopMark plugin authors.

These Protocols define stable, public contracts for third-party integrations that want to
add file types and header processors without importing TopMark's internal base classes.

You do not inherit from these Protocols at runtime; you implement the same attributes so that
type checkers (pyright/mypy) can validate your integration.

Stability policy:
- Attribute names and types here follow semver.
- Adding new optional attributes is allowed in minor releases.
- Removing/renaming attributes or changing types is a breaking change.

Diagnostics:
- The public API uses JSON-friendly diagnostics with string literal severities.
- See [`DiagnosticEntry`][topmark.api.types.DiagnosticEntry] for the stable shape and
  [`DiagnosticLevelLiteral`][topmark.api.types.DiagnosticLevelLiteral] for allowed values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol
from typing import TypedDict

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence
    from pathlib import Path


class PublicFileType(Protocol):
    """Minimal public contract for a file type.

    Attributes provide the **discovery metadata** TopMark needs to recognize files
    and determine whether a header can be managed. Instances are registered via the
    public registry, and may be **recognized but unsupported** (``skip_processing``)
    to enable reporting without modification.

    Required attributes:
        name: Stable identifier (e.g. ``"jsonc"``). Must be unique.
        description: Short human description for UI/logs.
        extensions: File extensions (without dot), e.g. ("json",).
        filenames: Exact file names (e.g. ("Makefile",)).
        patterns: Glob-like patterns (e.g. ("*.cfg",)).
        skip_processing: If ``True``, TopMark will not add/update/remove a header
            even if the type matches (still discoverable for reporting).
        header_policy_name: Symbolic policy name used by TopMark to guide header
            placement (e.g. "line", "block", or a custom policy).

    Optional:
        content_matcher: ``Callable[[Path], bool]`` that returns ``True`` **only**
            if the *file contents* confirm this specific type. Use this to
            disambiguate overlapping extensions, e.g. JSON-with-comments (JSONC)
            vs. plain JSON. The callable should be **cheap** and **side-effect free**;
            it must not modify files.
    """

    name: str
    description: str
    extensions: Sequence[str]
    filenames: Sequence[str]
    patterns: Sequence[str]
    skip_processing: bool
    content_matcher: Callable[[Path], bool] | None = None
    header_policy_name: str


class PublicPolicy(TypedDict, total=False):
    """Public, JSON-friendly policy overlay.

    This structure mirrors a subset of the internal policy and can be passed
    to `topmark.api.check()` / `topmark.api.strip()` to refine intent. All keys
    are optional; unspecified options inherit from project/default config.

    Keys:
        add_only: Only add missing headers; do not update existing ones.
        update_only: Only update existing headers; do not add new ones.
        allow_header_in_empty_files: Allow inserting headers in empty files (e.g., `__init__.py`).
        render_empty_header_when_no_fields: Allow inserting empty headers when no fields are
            defined.
        allow_reflow: If True, allow reflowing file content when inserting a header. This
            potentially breaks check/strip idempotence.
        allow_content_probe: Whether the resolver may consult file contents during file-type
            detection. True allows content-based probes, False forces name/extension-only
            resolution.

    Notes:
        This is a stable public contract; the internal policy may have additional
        fields introduced over time. Unknown keys are ignored.
    """

    add_only: bool
    update_only: bool
    allow_header_in_empty_files: bool
    render_empty_header_when_no_fields: bool
    allow_reflow: bool
    allow_content_probe: bool


class PublicPolicyByType(TypedDict, total=False):
    """Per-file-type public policy overlays.

    A mapping from file type identifier (e.g., `"python"`) to a
    `PublicPolicy` overlay that applies only to that type.

    Example:
        {"python": {"allow_header_in_empty_files": True}}

    Notes:
        Keys must match registered file type identifiers.
    """

    # keys are file type identifiers (e.g., "python"); values are PublicPolicy
    # e.g. {"python": {"allow_header_in_empty_files": True}}


class PublicHeaderProcessor(Protocol):
    """Minimal public contract for a header processor bound to one file type.

    Implementors expose comment delimiters and are attached to a file type during
    registration. At bind time, the registry sets ``file_type`` on the processor
    instance.

    Required attributes:
        description: Short human description for UI/logs.
        line_prefix/line_suffix: Line comment delimiters (if applicable).
        block_prefix/block_suffix: Block comment delimiters (if applicable).
        file_type: The bound [`PublicFileType`][topmark.api.protocols.PublicFileType] instance
            (set by registry).

    Notes:
        A processor represents the **behavior** for rendering, scanning and
        placing the TopMark header. It is separate from a file type, which
        represents **recognition metadata**.
    """

    description: str
    # optional metadata
    line_prefix: str
    line_suffix: str
    block_prefix: str
    block_suffix: str
    # registry binds at runtime
    file_type: PublicFileType
