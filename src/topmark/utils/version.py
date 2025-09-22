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

import re

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


def pep440_to_semver(pep440_version: str) -> str:
    """Convert (our) PEP 440 to SemVer.

    Maps:
      rcN  -> -rc.N
      aN   -> -alpha.N
      bN   -> -beta.N
      devN -> -dev.N (after any pre-release)
      +local kept as-is

    Args:
        pep440_version (str): The version in PEP 440 format

    Returns:
        str: The version in SemVer format.

    Raises:
        ValueError: on post releases.
    """
    m: re.Match[str] | None = _PEP440_RE.match(pep440_version)
    if not m:
        raise ValueError(f"Not a recognized PEP 440 version: {pep440_version!r}")
    if m.group("post") is not None:
        raise ValueError(f"Post-releases are not valid SemVer: {pep440_version!r}")
    major, minor, patch = m.group("major"), m.group("minor"), m.group("patch")
    base: str = f"{major}.{minor}.{patch}"
    pre = ""
    if m.group("pre_label"):
        lbl: str = {"a": "alpha", "b": "beta", "rc": "rc"}[m.group("pre_label")]
        pre: str = f"-{lbl}.{m.group('pre_num')}"
    dev: str = f"{'.' if pre else '-'}dev.{m.group('dev')}" if m.group("dev") else ""
    local: str = f"+{m.group('local')}" if m.group("local") else ""
    return f"{base}{pre}{dev}{local}"
