# topmark:header:start
#
#   project      : TopMark
#   file         : version.py
#   file_relpath : src/topmark/utils/version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Version utilities for TopMark."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from topmark.core.constants import MAX_VERSION_MAJOR
from topmark.core.constants import MAX_VERSION_MINOR
from topmark.core.constants import MIN_VERSION_MAJOR
from topmark.core.constants import MIN_VERSION_MINOR
from topmark.core.constants import TOPMARK
from topmark.core.constants import TOPMARK_VERSION
from topmark.version.convert import convert_pep440_to_semver


@dataclass(frozen=True, kw_only=True, slots=True)
class ComputedVersion:
    """Computed package version text and format metadata.

    Attributes:
        version_text: The effective version string.
        version_format: The format of `version_text`, such as `"pep440"` or `"semver"`.
        error: Conversion error when SemVer conversion was requested but failed.
    """

    version_text: str
    version_format: str
    error: Exception | None = None


def compute_version_text(
    *,
    semver: bool,
) -> ComputedVersion:
    """Compute the version string for TopMark.

    Args:
        semver: If True, attempt to convert the package's PEP 440 version to SemVer.

    Returns:
        Tuple (`version_text`, `version_format`, `error`).

        If SemVer conversion is requested and fails, TopMark falls back to the original
        PEP 440 version string and returns:
            - version_text: the PEP 440 version
            - version_format: "pep440"
            - error: the conversion exception

        If SemVer conversion succeeds (or semver=False), `error` is None.
    """
    version_text: str = TOPMARK_VERSION
    version_format: str = "pep440"
    error: Exception | None = None

    if semver:
        try:
            version_text = convert_pep440_to_semver(version_text)
            version_format = "semver"
        except ValueError as err:
            # Fall back to PEP440 and report the error
            error = err
    return ComputedVersion(
        version_text=version_text,
        version_format=version_format,
        error=error,
    )


# Simple runtime safety check (Optional but recommended)
def check_python_version() -> None:
    """Check if the current Python version is supported by TopMark."""
    current_version: tuple[int, int] = (sys.version_info[0], sys.version_info[1])
    min_version: tuple[int, int] = (MIN_VERSION_MAJOR, MIN_VERSION_MINOR)
    max_version: tuple[int, int] = (MAX_VERSION_MAJOR, MAX_VERSION_MINOR)
    if current_version < min_version or current_version >= max_version:
        print(  # noqa: T201
            f"Error: {TOPMARK} v{TOPMARK_VERSION} requires "
            f"Python {MIN_VERSION_MAJOR}.{MIN_VERSION_MINOR} through "
            f"{MAX_VERSION_MAJOR}.{MAX_VERSION_MINOR - 1}.\n"
            f"Current version: {sys.version.split()[0]}",
            file=sys.stderr,
        )
        sys.exit(1)
