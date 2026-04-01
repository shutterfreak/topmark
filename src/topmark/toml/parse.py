# topmark:header:start
#
#   project      : TopMark
#   file         : parse.py
#   file_relpath : src/topmark/toml/parse.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Split-parse helpers for TopMark TOML sources.

This module defines the per-source parse result used when reading a single
TopMark TOML document. A parsed source may contribute three distinct semantic
channels:

- layered configuration tables that later deserialize into `MutableConfig`
- non-layered writer preferences from `[writer]`
- discovery/config-loading metadata from `[config]`

This module is intentionally pure and TOML-facing:
- no file I/O
- no merge or precedence resolution
- no deserialization into `MutableConfig`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.config.types import FileWriteStrategy
from topmark.runtime.writer_options import WriterOptions
from topmark.toml.keys import Toml

if TYPE_CHECKING:
    from topmark.toml.types import TomlTable


@dataclass(frozen=True, slots=True)
class DiscoveryTomlOptions:
    """Discovery and config-loading metadata parsed from TOML.

    This is a pure per-source metadata carrier. These options do not
    participate in layered config merging.

    Attributes:
        root: If `True`, stop config discovery above the directory containing
            this TOML source. `None` means that the TOML source does not set a
            discovery boundary.
        strict_config_checking: If `True`, treat config warnings as errors
            while checking TOML configuration. `None` means that the TOML
            source does not specify a strictness preference.
    """

    root: bool | None = None
    strict_config_checking: bool | None = None


@dataclass(frozen=True, slots=True)
class ParsedTopmarkToml:
    """Per-source split parse result for a TopMark TOML document.

    This is not a merged or resolved result.

    Attributes:
        layered_config: Layered TOML fragment extracted from the source. This
            fragment participates in normal config-layer deserialization and
            merging.
        writer_options: Non-layered writer preferences parsed from the
            `[writer]` table, if present.
        discovery_options: Discovery and config-loading metadata parsed from
            the `[config]` table.
    """

    layered_config: TomlTable
    writer_options: WriterOptions | None
    discovery_options: DiscoveryTomlOptions


def parse_topmark_toml_table(data: TomlTable) -> ParsedTopmarkToml:
    """Split a TopMark TOML table into its semantic domains.

    Args:
        data: A TopMark TOML table, already normalized to plain-Python TOML
            structures.

    Returns:
        The per-source split parse result.
    """
    config_tbl: TomlTable | None = _get_table(data, Toml.SECTION_CONFIG)
    writer_tbl: TomlTable | None = _get_table(data, Toml.SECTION_WRITER)

    return ParsedTopmarkToml(
        layered_config=extract_layered_config_toml(data),
        writer_options=parse_writer_options(writer_tbl),
        discovery_options=parse_discovery_toml_options(config_tbl),
    )


def parse_discovery_toml_options(config_tbl: TomlTable | None) -> DiscoveryTomlOptions:
    """Parse discovery/config-loading metadata from the `[config]` table.

    Args:
        config_tbl: Parsed `[config]` table, or `None` when absent.

    Returns:
        Parsed discovery/config-loading metadata.
    """
    if config_tbl is None:
        return DiscoveryTomlOptions()

    root_value: object = config_tbl.get(Toml.KEY_ROOT)
    strict_value: object = config_tbl.get(Toml.KEY_STRICT_CONFIG_CHECKING)

    return DiscoveryTomlOptions(
        root=root_value if isinstance(root_value, bool) else None,
        strict_config_checking=strict_value if isinstance(strict_value, bool) else None,
    )


def parse_writer_options(writer_tbl: TomlTable | None) -> WriterOptions | None:
    """Parse persisted writer preferences from the `[writer]` table.

    Args:
        writer_tbl: Parsed `[writer]` table, or `None` when absent.

    Returns:
        Parsed writer options, or `None` when the table is absent or does not
        contain a valid persisted writer preference.
    """
    if writer_tbl is None:
        return None

    strategy_value: object = writer_tbl.get(Toml.KEY_STRATEGY)
    if not isinstance(strategy_value, str) or not strategy_value:
        return None

    try:
        strategy: FileWriteStrategy = FileWriteStrategy(strategy_value)
    except ValueError:
        return None

    return WriterOptions(file_write_strategy=strategy)


def extract_layered_config_toml(data: TomlTable) -> TomlTable:
    """Return only the layered-config sections from a TopMark TOML table.

    Args:
        data: Full TopMark TOML table.

    Returns:
        A shallow-copy TOML table containing only sections that participate in
        layered config deserialization.
    """
    out: TomlTable = {}

    for section in (
        Toml.SECTION_HEADER,
        Toml.SECTION_FIELDS,
        Toml.SECTION_FORMATTING,
        Toml.SECTION_POLICY,
        Toml.SECTION_POLICY_BY_TYPE,
        Toml.SECTION_FILES,
    ):
        table: TomlTable | None = _get_table(data, section)
        if table is not None:
            out[section] = dict(table)

    return out


def _get_table(data: TomlTable, section: str) -> TomlTable | None:
    """Return a named TOML subtable when present and well-formed."""
    value: object = data.get(section)
    return dict(value) if isinstance(value, dict) else None
