# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/version/types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Types for TopMark version reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VersionFormatLiteral = Literal["pep440", "semver"]
"""Version identifier format."""


@dataclass(frozen=True, slots=True)
class VersionInfo:
    """Prepared payload for `topmark version` (and the API equivalent).

    `VersionInfo` is part of the stable API surface.

    Attributes:
        version_text: TopMark version text in the requested output format.
        version_format: The format of `version_text` ("pep440" or "semver").
        err: Conversion error when `semver=True` and conversion fails. In that case
            `version_text` remains the original PEP 440 string and `version_format`
            is "pep440".
    """

    version_text: str
    version_format: VersionFormatLiteral
    err: Exception | None
