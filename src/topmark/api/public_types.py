# topmark:header:start
#
#   file         : public_types.py
#   file_relpath : src/topmark/api/public_types.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public Protocols for TopMark plugin authors.

These Protocols define the **stable, public contracts** for third‑party
integrations that want to add file types and header processors without
importing TopMark's internal base classes. Implement these Protocols in your
extension and register the instances through :mod:`topmark.registry`.

Notes:
    * These are *structural* Protocols used for static typing (mypy/pyright).
      You do not inherit from them; you implement the same attributes.
    * Attribute names and types here are part of the public API and follow
      semver. Adding optional attributes is allowed in minor versions; removing
      or changing types is a breaking change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Sequence

if TYPE_CHECKING:
    from collections.abc import Callable
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


class PublicHeaderProcessor(Protocol):
    """Minimal public contract for a header processor bound to one file type.

    Implementors expose comment delimiters and are attached to a file type during
    registration. At bind time, the registry sets ``file_type`` on the processor
    instance.

    Required attributes:
        description: Short human description for UI/logs.
        line_prefix/line_suffix: Line comment delimiters (if applicable).
        block_prefix/block_suffix: Block comment delimiters (if applicable).
        file_type: The bound :class:`PublicFileType` instance (set by registry).

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
