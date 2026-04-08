# topmark:header:start
#
#   project      : TopMark
#   file         : toml.py
#   file_relpath : tests/helpers/toml.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared TOML-layer test helpers.

This module contains reusable helpers for TOML-related tests that operate at
the boundary between:
    - `topmark.toml` (whole-source loading, extraction, and schema validation)
    - `topmark.config` (layered config deserialization)

The helpers here are intentionally pure (non-pytest-specific) so they can be
reused across multiple test modules without relying on `conftest.py` import
magic.

Typical responsibilities:
    - take a split-parsed `ParsedTopmarkToml`
    - deserialize its layered config fragment into `MutableConfig`
    - replay TOML schema validation issues into `draft.diagnostics`

These helpers complement the higher-level fixtures in
`tests/toml/conftest.py`, which provide ergonomic test entrypoints for
in-memory and file-based TOML sources.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.io.deserializers import mutable_config_from_layered_toml_table
from topmark.toml.validation import add_toml_issues

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.toml.parse import ParsedTopmarkToml


# ---- Shared TOML test helpers ----


def draft_from_parsed_topmark_toml(
    parsed: ParsedTopmarkToml,
    *,
    config_file: Path | None,
) -> MutableConfig:
    """Build a draft config from one already split-parsed TopMark TOML source.

    This helper centralizes the shared TOML/config boundary tail used by the
    TOML-layer test fixtures:
        1. deserialize the layered config fragment into `MutableConfig`,
        2. replay TOML schema validation issues into `draft.diagnostics`.

    Args:
        parsed: Already split-parsed TopMark TOML source.
        config_file: Optional source path used for relative-path normalization
            and config-file provenance.

    Returns:
        Layered config draft with TOML schema diagnostics attached.
    """
    draft: MutableConfig = mutable_config_from_layered_toml_table(
        parsed.layered_config,
        config_file=config_file,
    )
    add_toml_issues(draft.diagnostics, parsed.validation_issues)
    return draft
