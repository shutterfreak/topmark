# topmark:header:start
#
#   project      : TopMark
#   file         : version.py
#   file_relpath : src/topmark/presentation/shared/version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for the CLI version command."""

from __future__ import annotations

from dataclasses import dataclass

from topmark.cli.errors import TopmarkCliVersionConversionError
from topmark.utils.version import compute_version_text


@dataclass(frozen=True, slots=True)
class VersionHumanReport:
    """Representation of version information.

    Attributes:
        version_text: The effective version string (SemVer or PEP 440).
        version_format: The effective format label (e.g. "semver" or "pep440").
        error: Optional conversion error when SemVer conversion was requested and failed.
        verbosity_level: Effective verbosity for gating extra details.
        quiet: Suppresses default TEXT output.
        styled: Whether to render the output styled.
    """

    version_text: str
    version_format: str
    error: TopmarkCliVersionConversionError | None
    verbosity_level: int
    quiet: bool
    styled: bool


def make_version_human_report(
    semver: bool,
    verbosity_level: int,
    quiet: bool,
    styled: bool,
) -> VersionHumanReport:
    """Create a VersionHumanReport instance.

    Args:
        semver: Whether to render the version in SemVer format (default: PEP440).
        verbosity_level: Effective verbosity level.
        quiet: Suppresses default TEXT output.
        styled: Whether to render the output styled.

    Returns:
        The ``VersionHumanReport`` object.
    """
    version_text, version_format, err = compute_version_text(semver=semver)

    return VersionHumanReport(
        version_text=version_text,
        version_format=version_format,
        error=TopmarkCliVersionConversionError(message=str(err)) if err else None,
        verbosity_level=verbosity_level,
        quiet=quiet,
        styled=styled,
    )
