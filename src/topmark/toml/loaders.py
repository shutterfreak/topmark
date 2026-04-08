# topmark:header:start
#
#   project      : TopMark
#   file         : loaders.py
#   file_relpath : src/topmark/toml/loaders.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Load and split-parse TopMark TOML documents.

This module provides low-level file I/O helpers for reading TOML documents from
the filesystem, normalizing them to plain-Python TOML tables, and turning one
TopMark TOML source into a per-source split parse result.

Responsibilities:
    - read raw TOML documents from disk
    - normalize `tomlkit` output into [`TomlTable`][topmark.toml.types.TomlTable]
    - extract `[tool.topmark]` from `pyproject.toml` sources when needed
    - delegate per-source split parsing to
      [`parse_topmark_toml_table`][topmark.toml.parse.parse_topmark_toml_table]

This module does not deserialize layered config into `MutableConfig` and does
not resolve precedence across multiple sources.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import tomlkit
from tomlkit.exceptions import ParseError as TomlkitParseError

from topmark.core.logging import get_logger
from topmark.core.typing_guards import as_object_dict
from topmark.toml.parse import ParsedTopmarkToml
from topmark.toml.parse import parse_topmark_toml_table
from topmark.toml.pyproject import extract_pyproject_topmark_table
from topmark.toml.schema import TOPMARK_TOML_SCHEMA
from topmark.toml.schema import TomlValidationMode
from topmark.toml.typing_guards import toml_table_from_mapping

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.core.logging import TopmarkLogger
    from topmark.toml.types import TomlTable
    from topmark.toml.validation import TomlValidationIssue

logger: TopmarkLogger = get_logger(__name__)


def _load_toml_table(path: Path) -> TomlTable | None:
    """Load one TOML document from disk as a plain-Python TOML table.

    Args:
        path: Path to a TOML document such as `topmark.toml` or `pyproject.toml`.

    Returns:
        The parsed TOML document normalized to a plain-Python TOML table, or
        `None` when the file cannot be read or parsed.

    Notes:
        - Errors are logged and `None` is returned on failure.
        - Encoding is assumed to be UTF-8.
        - `tomlkit` documents are unwrapped and normalized before being
          returned.
    """
    # Load with UTF-8, parse with tomlkit, then normalize to the plain
    # Python TOML shapes used throughout `topmark.toml`.
    try:
        text: str = path.read_text(encoding="utf-8")
        doc: tomlkit.TOMLDocument = tomlkit.parse(text)
        unwrapped: object = doc.unwrap()
        return toml_table_from_mapping(as_object_dict(unwrapped))
    except OSError as e:
        logger.error("Error loading TOML from %s: %s", path, e)
        return None
    except TomlkitParseError as e:
        logger.error("Error parsing TOML from %s: %s", path, e)
        return None
    except (TypeError, ValueError) as e:
        logger.error("Error normalizing TOML from %s: %s", path, e)
        return None


def _load_topmark_toml_table(
    data: TomlTable,
    *,
    source_path: Path | None = None,
    from_pyproject: bool = False,
) -> ParsedTopmarkToml | None:
    """Split-parse an in-memory TopMark TOML source table.

    Args:
        data: In-memory TOML table representing either a full TopMark TOML
            document or a parsed `pyproject.toml` document.
        source_path: Optional source path used only for diagnostics/logging.
        from_pyproject: If `True`, first extract `[tool.topmark]` from the TOML
            document before split parsing.

    Returns:
        The per-source split parse result, or `None` when `from_pyproject=True`
        and no valid `[tool.topmark]` table is present.
    """
    # `pyproject.toml` embeds TopMark settings under `[tool.topmark]`; plain
    # `topmark.toml` already exposes the relevant source table directly.
    topmark_tbl: TomlTable | None = (
        extract_pyproject_topmark_table(data) if from_pyproject else data
    )
    if topmark_tbl is None:
        logger.debug(
            "No [tool.topmark] table found in %s",
            source_path if source_path is not None else "<in-memory TOML>",
        )
        return None

    # Validate the TOML schema
    issues: tuple[TomlValidationIssue, ...] = TOPMARK_TOML_SCHEMA.validate(
        topmark_tbl,
        mode=TomlValidationMode.INPUT,
    )

    # Delegate semantic splitting of the TOML source to the pure parser layer.
    return parse_topmark_toml_table(
        topmark_tbl,
        validation_issues=issues,
    )


def load_topmark_toml_source(path: Path) -> ParsedTopmarkToml | None:
    """Load and split-parse one TopMark TOML source file.

    Args:
        path: Path to a TopMark TOML source file.

    Returns:
        The per-source split parse result, or `None` when the file cannot be
        loaded or does not contain a valid TopMark TOML source table.
    """
    data: TomlTable | None = _load_toml_table(path)
    if data is None:
        return None

    return _load_topmark_toml_table(
        data,
        source_path=path,
        from_pyproject=path.name == "pyproject.toml",
    )
