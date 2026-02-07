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

import re
import sys

from topmark.constants import (
    MIN_VERSION_MAJOR,
    MIN_VERSION_MINOR,
    TOPMARK,
    TOPMARK_VERSION,
)

# Recognize the subset of PEP 440 we actually emit:
#   X.Y.Z
#   X.Y.ZrcN
#   X.Y.ZaN / X.Y.ZbN
#   X.Y.Z.devN
#   +local (optional)
# We deliberately do NOT accept .postN here (no clean SemVer equivalent).
_PEP440_RE: re.Pattern[str] = re.compile(
    r"""
    ^
    (?P<major>0|[1-9]\d*)\.
    (?P<minor>0|[1-9]\d*)\.
    (?P<patch>0|[1-9]\d*)
    (?:
      (?P<pre_label>a|b|rc)(?P<pre_num>\d+)
    )?
    (?:
      \.post(?P<post>\d+)
    )?
    (?:
      \.dev(?P<dev>\d+)
    )?
    (?:
      \+(?P<local>[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)
    )?
    $
    """,
    re.VERBOSE,
)


def convert_pep440_to_semver(pep440_version: str) -> str:
    """Convert a PEP 440 version string to a SemVer-compatible string.

    Maps:
      rcN  -> -rc.N
      aN   -> -alpha.N
      bN   -> -beta.N
      devN -> -dev.N (after any pre-release)
      +local kept as-is

    Args:
        pep440_version: The version in PEP 440 format

    Returns:
        The version in SemVer format.

    Raises:
        ValueError: on post releases.
    """
    m: re.Match[str] | None = _PEP440_RE.match(pep440_version)
    if not m:
        raise ValueError(f"Not a recognized PEP 440 version: {pep440_version!r}")
    if m.group("post") is not None:
        raise ValueError(f"Post-releases are not valid SemVer: {pep440_version!r}")
    major: str | None = None
    minor: str | None = None
    patch: str | None = None
    major, minor, patch = m.group("major"), m.group("minor"), m.group("patch")
    base: str = f"{major}.{minor}.{patch}"
    pre: str = ""
    if m.group("pre_label"):
        lbl: str = {"a": "alpha", "b": "beta", "rc": "rc"}[m.group("pre_label")]
        pre = f"-{lbl}.{m.group('pre_num')}"
    dev: str = f"{'.' if pre else '-'}dev.{m.group('dev')}" if m.group("dev") else ""
    local: str = f"+{m.group('local')}" if m.group("local") else ""
    return f"{base}{pre}{dev}{local}"


def compute_version_text(
    *,
    semver: bool,
) -> tuple[str, str, Exception | None]:
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
    return version_text, version_format, error


# Simple runtime safety check (Optional but recommended)
def check_python_version() -> None:
    """Check if the current Python version meets the minimum requirement."""
    if sys.version_info < (MIN_VERSION_MAJOR, MIN_VERSION_MINOR):
        print(  # noqa: T201
            f"Error: {TOPMARK} v{TOPMARK_VERSION} requires "
            f"Python {MIN_VERSION_MAJOR}.{MIN_VERSION_MINOR} or higher.\n"
            f"Current version: {sys.version.split()[0]}",
            file=sys.stderr,
        )
        sys.exit(1)
