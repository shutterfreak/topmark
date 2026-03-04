# topmark:header:start
#
#   project      : TopMark
#   file         : runtime.py
#   file_relpath : src/topmark/version/runtime.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Compute TopMark `VersionInfo` and optionally convert to SemVer-ish output."""

from __future__ import annotations

from topmark.constants import TOPMARK_VERSION
from topmark.version.convert import convert_pep440_to_semver
from topmark.version.types import VersionFormatLiteral
from topmark.version.types import VersionInfo


def compute_version_info(
    *,
    semver: bool,
) -> VersionInfo:
    """Compute the version information payload for TopMark.

    Args:
        semver: If True, attempt to convert the package's PEP 440 version to a SemVer-ish
            representation.

    Returns:
        A `VersionInfo` instance.

        - When `semver=False`, returns PEP 440 version with `err=None`.
        - When `semver=True` and conversion succeeds, returns SemVer-ish version with `err=None`.
        - When `semver=True` and conversion fails, returns the original PEP 440 version with
            `version_format="pep440"` and `err=<conversion exception>`.
    """
    version_text: str = TOPMARK_VERSION
    version_format: VersionFormatLiteral = "pep440"
    err: Exception | None = None

    if semver:
        try:
            version_text = convert_pep440_to_semver(version_text)
            version_format = "semver"
        except ValueError as exc:
            # Fall back to PEP 440 and report the conversion error.
            err = exc
    return VersionInfo(
        version_text=version_text,
        version_format=version_format,
        err=err,
    )
