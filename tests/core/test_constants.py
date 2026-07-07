# topmark:header:start
#
#   project      : TopMark
#   file         : test_constants.py
#   file_relpath : tests/core/test_constants.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for TopMark's core constants and metadata helpers."""

from __future__ import annotations

import importlib
import importlib.metadata as importlib_metadata
import re
import sys
from email.message import Message
from typing import TYPE_CHECKING

import pytest

import topmark.core.constants as constants
from topmark.core.constants import DependencyInfo

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType


@pytest.fixture
def restore_constants_module() -> Iterator[None]:
    """Reload constants after tests that exercise import-time metadata branches."""
    try:
        yield
    finally:
        importlib.reload(constants)


# --- Package metadata resolution ---


def test_resolve_topmark_version_falls_back_without_generated_or_installed_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Version resolution should remain stable in unpackaged source-tree contexts."""

    def missing_metadata_version(_package_name: str) -> str:
        raise importlib_metadata.PackageNotFoundError

    monkeypatch.setitem(
        sys.modules,
        "topmark._version",
        None,
    )
    monkeypatch.setattr(
        constants,
        "metadata_version",
        missing_metadata_version,
    )

    # Exercise the fallback branch directly because it is otherwise import-time only.
    assert constants._resolve_topmark_version() == "0.0.0.dev0"  # pyright: ignore[reportPrivateUsage]


def test_constants_use_stable_fallbacks_when_distribution_metadata_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    restore_constants_module: None,
) -> None:
    """Import-time constants should remain usable when package metadata is absent."""

    def missing_metadata(_package_name: str) -> Message:
        raise importlib_metadata.PackageNotFoundError

    monkeypatch.setattr(
        importlib_metadata,
        "metadata",
        missing_metadata,
    )

    reloaded: ModuleType = importlib.reload(constants)

    assert reloaded.TOPMARK == "topmark"
    assert reloaded.TOPMARK_VERSION == "0.0.0.dev0"
    assert reloaded.DESCRIPTION == "A Python CLI to inspect and manage license headers."
    assert reloaded.LICENSE == "MIT"
    assert reloaded.REQUIRES_PYTHON == ">=3.10"
    assert reloaded.DEPENDENCIES == []
    assert reloaded.DEV_DEPENDENCIES == []
    assert reloaded.DOCS_DEPENDENCIES == []
    assert reloaded.TEST_DEPENDENCIES == []


# --- Dependency metadata bucketing ---


def test_dependency_metadata_buckets_core_and_extra_requirements(
    monkeypatch: pytest.MonkeyPatch,
    restore_constants_module: None,
) -> None:
    """Requires-Dist metadata should be split into core and named extra buckets."""
    package_metadata = Message()
    package_metadata["Name"] = "TopMark"
    package_metadata["Summary"] = "Metadata-backed summary"
    package_metadata["License-Expression"] = "MIT"
    package_metadata["Requires-Python"] = ">=3.10"
    package_metadata["Requires-Dist"] = "click>=8.2"
    package_metadata["Requires-Dist"] = "coverage; extra == 'test'"
    package_metadata["Requires-Dist"] = "mkdocs; extra == 'docs'"
    package_metadata["Requires-Dist"] = "ruff; python_version >= '3.10'"
    package_metadata["Requires-Dist"] = "mypy; extra == 'dev'"

    def package_metadata_for(_package_name: str) -> Message:
        return package_metadata

    def package_version_for(_package_name: str) -> str:
        return "2.0.0"

    monkeypatch.setattr(
        importlib_metadata,
        "metadata",
        package_metadata_for,
    )
    monkeypatch.setattr(
        importlib_metadata,
        "version",
        package_version_for,
    )
    monkeypatch.setitem(
        sys.modules,
        "topmark._version",
        None,
    )

    reloaded: ModuleType = importlib.reload(constants)

    assert reloaded.TOPMARK == "TopMark"
    assert reloaded.DESCRIPTION == "Metadata-backed summary"
    assert reloaded.LICENSE == "MIT"
    assert reloaded.REQUIRES_PYTHON == ">=3.10"
    assert [
        DependencyInfo(
            name="click",
            specifier=">=8.2",
        ),
        DependencyInfo(
            name="ruff",
            specifier="",
        ),
    ] == reloaded.DEPENDENCIES
    assert [
        DependencyInfo(
            name="coverage",
            specifier="",
        )
    ] == reloaded.TEST_DEPENDENCIES
    assert [
        DependencyInfo(
            name="mkdocs",
            specifier="",
        )
    ] == reloaded.DOCS_DEPENDENCIES
    assert [
        DependencyInfo(
            name="mypy",
            specifier="",
        )
    ] == reloaded.DEV_DEPENDENCIES


def test_dependency_metadata_falls_back_to_core_when_extra_marker_cannot_be_extracted(
    monkeypatch: pytest.MonkeyPatch,
    restore_constants_module: None,
) -> None:
    """Dependency bucketing should fail open when an extra marker cannot be parsed."""
    package_metadata = Message()
    package_metadata["Requires-Dist"] = "pluggy; extra == 'test'"

    def package_metadata_for(_package_name: str) -> Message:
        return package_metadata

    def package_version_for(_package_name: str) -> str:
        return "2.0.0"

    def no_marker_match(_pattern: str, _string: str) -> None:
        return None

    monkeypatch.setattr(
        importlib_metadata,
        "metadata",
        package_metadata_for,
    )
    monkeypatch.setattr(
        importlib_metadata,
        "version",
        package_version_for,
    )
    monkeypatch.setattr(
        re,
        "search",
        no_marker_match,
    )
    monkeypatch.setitem(
        sys.modules,
        "topmark._version",
        None,
    )

    reloaded: ModuleType = importlib.reload(constants)

    assert [
        DependencyInfo(
            name="pluggy",
            specifier="",
        )
    ] == reloaded.DEPENDENCIES
    assert reloaded.TEST_DEPENDENCIES == []


# --- Public constants ---


def test_public_constants_expose_stable_identity_markers_and_newline_contracts() -> None:
    """Low-level constants should expose stable values used across project layers."""
    assert constants.PACKAGE_NAME == "topmark"
    assert constants.DISPLAY_NAME == "TopMark"
    assert constants.MIN_VERSION_MAJOR == 3
    assert constants.MIN_VERSION_MINOR == 10
    assert constants.TOPMARK_NAMESPACE == "topmark"
    assert constants.TOPMARK_START_MARKER == "topmark:header:start"
    assert constants.TOPMARK_END_MARKER == "topmark:header:end"
    assert constants.TOML_BLOCK_START == "# === BEGIN[TOML] ==="
    assert constants.TOML_BLOCK_END == "# === END[TOML] ==="
    assert constants.STANDARD_NEWLINES == (
        "\r\n",
        "\n",
        "\r",
    )
    assert (
        frozenset(
            {
                "\r\n",
                "\n",
                "\r",
            }
        )
        == constants.STANDARD_NEWLINE_SET
    )
    assert constants.STANDARD_NEWLINE_RE == r"\r\n|\n|\r"
