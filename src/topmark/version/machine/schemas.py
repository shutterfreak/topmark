# topmark:header:start
#
#   project      : TopMark
#   file         : schemas.py
#   file_relpath : src/topmark/version/machine/schemas.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Stable schema enums for version-related machine output.

This module contains the version-domain keys and NDJSON kinds used by the
version machine-output package. Shared envelope keys remain in
`topmark.core.machine.schemas`, while shared diagnostic keys and diagnostic
record kinds live in `topmark.diagnostic.machine.schemas`.
"""

from __future__ import annotations

from enum import Enum


class VersionKey(str, Enum):
    """Stable version-domain keys for machine-readable payloads.

    Attributes:
        VERSION: Effective rendered version string.
        VERSION_INFO: Container key for the JSON version payload.
        VERSION_FORMAT: String describing the effective version format.
    """

    VERSION = "version"
    VERSION_INFO = "version_info"
    VERSION_FORMAT = "version_format"


class VersionKind(str, Enum):
    """Stable NDJSON kinds emitted by the version machine-output domain.

    Attributes:
        VERSION: One version-information record.
    """

    VERSION = "version"
