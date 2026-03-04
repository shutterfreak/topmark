# topmark:header:start
#
#   project      : TopMark
#   file         : version.py
#   file_relpath : src/topmark/api/commands/version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Version metadata helpers (public API).

`get_version_info()` returns a structured `VersionInfo` object.
`get_version_text()` returns a user-facing version string.

The canonical `VersionInfo` definition lives in `topmark.version.types`. The public API façade
re-exports `VersionInfo` so consumers can import it from `topmark.api` without depending on
internal module paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.version.runtime import compute_version_info

if TYPE_CHECKING:
    from topmark.version.types import VersionInfo

__all__ = (
    "get_version_info",
    "get_version_text",
)


def get_version_info(*, semver: bool = False) -> VersionInfo:
    """Return the current TopMark version info."""
    return compute_version_info(semver=semver)


def get_version_text() -> str:
    """Return the current TopMark version (string)."""
    # Convenience string form for UI/logging; structured metadata is in `get_version_info()`.
    return get_version_info(semver=False).version_text
