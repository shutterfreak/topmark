# topmark:header:start
#
#   project      : TopMark
#   file         : documentation.py
#   file_relpath : src/topmark/cli/documentation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Build version-aware links to hosted TopMark documentation."""

from __future__ import annotations

from packaging.version import InvalidVersion
from packaging.version import Version

from topmark.core.constants import DOCS_BASE_URL
from topmark.core.constants import TOPMARK_VERSION


def documentation_version_slug(
    version: str,
) -> str:
    """Return the Read the Docs version slug appropriate for a package version.

    Development, local, and invalid builds link to the default-branch
    documentation at ``latest``. Tagged releases use TopMark's
    ``v<public-version>`` Git-tag convention, which is also the Read the Docs
    version slug.

    Args:
        version: Resolved TopMark package version in PEP 440 form.

    Returns:
        The Read the Docs version slug for the version.
    """
    try:
        parsed_version = Version(version)
    except InvalidVersion:
        return "latest"
    if parsed_version.is_devrelease or parsed_version.local is not None:
        return "latest"
    return f"v{parsed_version.public}"


def command_reference_url(
    path: str,
    *,
    version: str = TOPMARK_VERSION,
) -> str:
    """Build the hosted documentation URL for a command-reference path.

    Args:
        path: Path below the hosted ``usage/`` documentation root, without a
            leading or trailing slash.
        version: Resolved TopMark package version in PEP 440 form.

    Returns:
        Version-aware absolute URL for the command reference.
    """
    version_slug: str = documentation_version_slug(version)
    return f"{DOCS_BASE_URL}/{version_slug}/usage/{path.strip('/')}/"
