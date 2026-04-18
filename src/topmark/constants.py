# topmark:header:start
#
#   project      : TopMark
#   file         : constants.py
#   file_relpath : src/topmark/constants.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark Constants."""

from __future__ import annotations

import contextlib
from collections import defaultdict
from importlib.metadata import PackageMetadata
from importlib.metadata import PackageNotFoundError
from importlib.metadata import metadata
from importlib.metadata import version as metadata_version
from pathlib import Path
from re import Match
from typing import TYPE_CHECKING
from typing import Final
from typing import TypedDict
from typing import cast

from packaging.requirements import Requirement

if TYPE_CHECKING:
    from collections.abc import Mapping

# 1. The bootstrap string (Distribution name in pyproject.toml)
# This MUST match the lowercase name in pyproject.toml for metadata resolution.
PACKAGE_NAME: Final = "topmark"

# Branded name for display/documentation
DISPLAY_NAME: Final = "TopMark"

# Minimal Python version
MIN_VERSION_MAJOR: Final[int] = 3
MIN_VERSION_MINOR: Final[int] = 10


class DependencyInfo(TypedDict):
    """Structural metadata for a single project dependency."""

    name: str
    specifier: str


def _resolve_topmark_version() -> str:
    """Resolve the TopMark version from generated code or installed metadata."""
    with contextlib.suppress(ImportError):
        from topmark._version import version as generated_version

        return generated_version
    try:
        return metadata_version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0.dev0"


try:
    # 2. Fetch metadata once
    _dist_meta: PackageMetadata = metadata(PACKAGE_NAME)
    # This returns a Message object containing all pyproject.toml [project] fields

    # 3. Resolve properties using Core Metadata keys
    # Cast to Mapping to satisfy Pyright regarding the .get() method
    _meta_map: Mapping[str, str] = cast("Mapping[str, str]", _dist_meta)

    _topmark: str = _meta_map.get("Name") or PACKAGE_NAME
    _version: str = _resolve_topmark_version()
    _description: str = _meta_map.get("Summary") or ""

    # Resolve License: Try License-Expression (PEP 639), then fallback to License
    _license: str = _meta_map.get("License-Expression") or _meta_map.get("License") or ""

    _requires_python: str = _meta_map.get("Requires-Python") or ""

    # 4. Structural Dependency Bucketing using packaging.requirements
    _all_deps: list[str] = _dist_meta.get_all("Requires-Dist") or []

    # Initialize buckets with defaultdict to handle any extra dynamically
    _buckets: dict[str, list[DependencyInfo]] = defaultdict(list)

    for d in _all_deps:
        req = Requirement(d)
        # Extract the 'extra' marker if it exists
        # Markers can be complex, but for pyproject extras they usually look like:
        # extra == 'dev'
        info: DependencyInfo = {
            "name": req.name,
            "specifier": str(req.specifier) if req.specifier else "",
        }
        found_extra = False
        if req.marker:
            # Look for the 'extra' marker variable
            # Use a safer way to check for the extra marker
            marker_str = str(req.marker)
            if "extra ==" in marker_str:
                # Extract the extra name from the marker string
                import re

                match: Match[str] | None = re.search(
                    r'extra\s*==\s*["\']([^"\']+)["\']', marker_str
                )
                if match:
                    extra_name: str = match.group(1)
                    _buckets[extra_name].append(info)
                    found_extra = True

        if not found_extra:
            # If no extra marker is found, it's a core dependency
            _buckets["core"].append(info)

    _dep_buckets: dict[str, list[DependencyInfo]] = dict(_buckets)

except (ImportError, PackageNotFoundError):
    # Fallback for local development if the package isn't 'pip install -e .' yet
    _topmark = PACKAGE_NAME
    _version = "0.0.0.dev0"
    _description = "A Python CLI to inspect and manage license headers."
    _license = "MIT"
    _requires_python = f">={MIN_VERSION_MAJOR}.{MIN_VERSION_MINOR}"
    _dep_buckets = {"core": []}

TOPMARK: Final = _topmark
TOPMARK_VERSION: Final = _version
DESCRIPTION: Final = _description
LICENSE: Final = _license
REQUIRES_PYTHON: Final = _requires_python

# Exported Dependency Lists (sorted by package name)
DEPENDENCIES: Final[list[DependencyInfo]] = sorted(
    _dep_buckets.get("core", []), key=lambda x: x["name"]
)
DEV_DEPENDENCIES: Final[list[DependencyInfo]] = sorted(
    _dep_buckets.get("dev", []), key=lambda x: x["name"]
)
DOCS_DEPENDENCIES: Final[list[DependencyInfo]] = sorted(
    _dep_buckets.get("docs", []), key=lambda x: x["name"]
)
TEST_DEPENDENCIES: Final[list[DependencyInfo]] = sorted(
    _dep_buckets.get("test", []), key=lambda x: x["name"]
)

# Using .resolve() ensures we have an absolute path regardless of CWD
PYPROJECT_TOML_PATH: Final = (Path(__file__).parent.parent.parent / "pyproject.toml").resolve()

# --- Global Markers ---

EXAMPLE_TOPMARK_TOML_PACKAGE: Final = "topmark.toml"
"""Package containing the bundled example TopMark TOML document `topmark-example.toml`."""

EXAMPLE_TOPMARK_TOML_NAME: Final = "topmark-example.toml"
"""Resource name of the bundled example TopMark TOML document."""

TOPMARK_START_MARKER: Final = "topmark:header:start"
"""Start marker of TopMark header."""
TOPMARK_END_MARKER: Final = "topmark:header:end"
"""End marker of TopMark header."""

TOML_BLOCK_START: Final = "# === BEGIN[TOML] ==="
TOML_BLOCK_END: Final = "# === END[TOML] ==="

# --- String constants ---

TOPMARK_NAMESPACE: Final = "topmark"
"""Namespace identifier for TopMark-provided registry entries."""

VALUE_NOT_SET: Final = "<not set>"

CLI_OVERRIDE_STR: Final = "<CLI overrides>"

# --- Patterns and Regular Expressions ---

VALID_REGISTRY_TOKEN_RE: Final = r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*"  # noqa: S105
"""Regular expression pattern applicable to `key` and `namespace` in the registry.

Rules:
    - Allowed characters: a-z, 0-9, '.', '_', '-'
    - Must start with a-z
    - Must not end with a separator ('.', '_', '-')
    - No consecutive separators
    - Must not contain ':'
"""
