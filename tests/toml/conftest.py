# topmark:header:start
#
#   project      : TopMark
#   file         : conftest.py
#   file_relpath : tests/toml/conftest.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared pytest helpers for TOML-layer tests.

This module hosts TOML-scoped test helpers used by `tests/toml/*` to exercise
TopMark's TOML loading boundary:
    - validate and split-parse full TopMark TOML sources,
    - deserialize only the layered config fragment,
    - and replay TOML schema diagnostics into `MutableConfig.diagnostics`.

These helpers intentionally sit at the TOML/config boundary so TOML-schema
validation tests can assert both the loader behavior and the resulting draft
config diagnostics without routing through the full CLI.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from tests.helpers.toml import draft_from_parsed_topmark_toml
from topmark.toml.loaders import load_topmark_toml_source
from topmark.toml.loaders import load_topmark_toml_table

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.toml.parse import ParsedTopmarkToml
    from topmark.toml.types import TomlTable


# ---- Shared TOML test helpers ----


def draft_from_topmark_toml_table(
    data: TomlTable,
    *,
    source_path: Path | None = None,
    from_pyproject: bool = False,
) -> MutableConfig:
    """Build a config draft from one in-memory TopMark TOML source table.

    This helper exercises the TOML/config boundary directly:
        1. validate and split-parse the full TopMark TOML source,
        2. deserialize only the layered config fragment,
        3. replay TOML schema validation issues into the draft diagnostics.

    Args:
        data: In-memory TopMark TOML table or parsed `pyproject.toml` table.
        source_path: Optional source path used for relative-path normalization.
        from_pyproject: Whether `data` represents a full `pyproject.toml`
            document requiring `[tool.topmark]` extraction.

    Returns:
        Layered config draft with TOML schema diagnostics attached.

    Raises:
        AssertionError: If the TOML source cannot be split-parsed.
    """
    parsed: ParsedTopmarkToml | None = load_topmark_toml_table(
        data,
        source_path=source_path,
        from_pyproject=from_pyproject,
    )
    assert parsed is not None, "Expected valid TopMark TOML source table"

    return draft_from_parsed_topmark_toml(
        parsed,
        config_file=source_path,
    )


def draft_from_topmark_toml_file(path: Path) -> MutableConfig:
    """Build a config draft from one file-backed TopMark TOML source.

    This is the file-based companion to `draft_from_topmark_toml_table()` and
    is used by TOML-schema tests that exercise `topmark.toml` loading from the
    filesystem.

    Args:
        path: Path to `topmark.toml` or `pyproject.toml`.

    Returns:
        Layered config draft deserialized from the split-parsed TOML source,
        with TOML schema diagnostics attached.

    Raises:
        AssertionError: If the TOML source cannot be loaded or split-parsed.
    """
    parsed: ParsedTopmarkToml | None = load_topmark_toml_source(path)
    assert parsed is not None, f"Expected valid TopMark TOML source: {path}"

    return draft_from_parsed_topmark_toml(
        parsed,
        config_file=path,
    )


def write_toml_document(
    *,
    path: Path,
    content: str,
) -> None:
    """Write a small TOML snippet to `path`, creating parent directories.

    This helper is primarily used by TOML and discovery-oriented tests that
    need compact on-disk fixtures without a larger temporary-project builder.

    Removes left indentation of TOML content.
    """
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        textwrap.dedent(content).lstrip("\n"),
        encoding="utf-8",
    )
