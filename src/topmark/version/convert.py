# topmark:header:start
#
#   project      : TopMark
#   file         : convert.py
#   file_relpath : src/topmark/version/convert.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Convert the subset of PEP 440 versions TopMark emits into SemVer-ish output.

Supported inputs (subset):
- X.Y.Z
- X.Y.ZaN / X.Y.ZbN / X.Y.ZrcN
- X.Y.Z.devN (or with a pre-release, e.g. X.Y.Zrc1.dev2)
- optional local version: +local (kept as-is)

Notes:
- `.postN` is recognized only so we can reject it with a clear error message,
  because it has no clean SemVer equivalent.
"""

from __future__ import annotations

import re

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
"""Pattern for the supported PEP 440 subset (including `.postN` for explicit rejection)."""


def convert_pep440_to_semver(pep440_version: str) -> str:
    """Convert a supported PEP 440 version string to a SemVer-ish string.

    Mapping:
      - rcN  -> -rc.N
      - aN   -> -alpha.N
      - bN   -> -beta.N
      - devN -> -dev.N (after any pre-release)
      - +local kept as-is

    Examples:
      - 1.2.3        -> 1.2.3
      - 1.2.3rc1     -> 1.2.3-rc.1
      - 1.2.3rc1.dev2 -> 1.2.3-rc.1.dev.2
      - 1.2.3.dev4   -> 1.2.3-dev.4
      - 1.2.3+abc.1  -> 1.2.3+abc.1

    Args:
        pep440_version: Version in PEP 440 format.

    Returns:
        A SemVer-ish version string.

    Raises:
        ValueError: If the version does not match the supported subset or if it contains `.postN`.
    """
    m: re.Match[str] | None = _PEP440_RE.match(pep440_version)
    if not m:
        raise ValueError(f"Not a recognized supported PEP 440 version: {pep440_version!r}")

    if m.group("post") is not None:
        raise ValueError(f"Post-releases are not valid SemVer: {pep440_version!r}")

    major: str = m.group("major")
    minor: str = m.group("minor")
    patch: str = m.group("patch")
    base: str = f"{major}.{minor}.{patch}"

    pre: str = ""
    pre_label: str | None = m.group("pre_label")
    if pre_label is not None:
        lbl: str = {"a": "alpha", "b": "beta", "rc": "rc"}[pre_label]
        pre = f"-{lbl}.{m.group('pre_num')}"

    dev: str = ""
    if m.group("dev") is not None:
        # If we already have a pre-release, dev becomes an extra dot-segment; otherwise it starts
        # the pre-release part.
        dev = f"{'.' if pre else '-'}dev.{m.group('dev')}"

    local: str = f"+{m.group('local')}" if m.group("local") else ""
    return f"{base}{pre}{dev}{local}"
