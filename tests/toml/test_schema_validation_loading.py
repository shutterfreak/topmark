# topmark:header:start
#
#   project      : TopMark
#   file         : test_schema_validation_loading.py
#   file_relpath : tests/toml/test_schema_validation_loading.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for file-based and pyproject-based TOML schema validation loading.

These tests cover TOML loading paths that go beyond in-memory table validation:
- extracting `[tool.topmark]` from `pyproject.toml`,
- distinguishing missing versus empty `tool.topmark` tables,
- and propagating whole-source TOML schema diagnostics through file-based
  loading helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import tomlkit

from tests.helpers.diagnostics import assert_warned_and_diagnosed
from tests.toml.conftest import draft_from_topmark_toml_file
from tests.toml.conftest import write_toml_document
from topmark.diagnostic.model import DiagnosticLevel
from topmark.toml.keys import Toml
from topmark.toml.loaders import load_topmark_toml_source
from topmark.toml.loaders import load_topmark_toml_table
from topmark.toml.validation import TomlDiagnosticCode

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.toml.parse import ParsedTopmarkToml
    from topmark.toml.types import TomlTable


# --- Pyproject extraction and source-loading validation ---


@pytest.mark.toml
def test_load_topmark_toml_table_extracts_tool_topmark_from_pyproject_table() -> None:
    """`load_topmark_toml_table(..., from_pyproject=True)` extracts `[tool.topmark]`."""
    pyproject_tbl: TomlTable = tomlkit.parse(
        """
        [tool.topmark.header]
        fields = ["file"]
        """
    ).unwrap()

    parsed: ParsedTopmarkToml | None = load_topmark_toml_table(
        pyproject_tbl,
        from_pyproject=True,
    )
    assert parsed is not None

    assert Toml.SECTION_HEADER in parsed.layered_config
    header_section = parsed.layered_config[Toml.SECTION_HEADER]

    assert isinstance(header_section, dict)
    assert Toml.KEY_FIELDS in header_section

    assert header_section[Toml.KEY_FIELDS] == ["file"]


@pytest.mark.toml
def test_load_topmark_toml_source_distinguishes_missing_vs_empty_tool_topmark(
    tmp_path: Path,
) -> None:
    """Missing `[tool.topmark]` returns `None`, while an empty table still parses.

    An empty table parses with missing-section INFO diagnostics.
    """
    missing_dir: Path = tmp_path / "missing"
    missing_dir.mkdir()
    missing_path: Path = missing_dir / "pyproject.toml"
    write_toml_document(
        path=missing_path,
        content="""
            [tool.other]
            value = 1
        """,
    )

    empty_dir: Path = tmp_path / "empty"
    empty_dir.mkdir()
    empty_path: Path = empty_dir / "pyproject.toml"
    write_toml_document(
        path=empty_path,
        content="""
            [tool.topmark]
        """,
    )

    missing_parsed: ParsedTopmarkToml | None = load_topmark_toml_source(missing_path)
    empty_parsed: ParsedTopmarkToml | None = load_topmark_toml_source(empty_path)

    assert missing_parsed is None
    assert empty_parsed is not None
    assert empty_parsed.layered_config == {}

    missing_sections = {
        issue.section
        for issue in empty_parsed.validation_issues
        if issue.code is TomlDiagnosticCode.MISSING_SECTION
    }

    assert missing_sections == {
        Toml.SECTION_CONFIG,
        Toml.SECTION_HEADER,
        Toml.SECTION_FIELDS,
        Toml.SECTION_FORMATTING,
        Toml.SECTION_WRITER,
        Toml.SECTION_POLICY,
        Toml.SECTION_POLICY_BY_TYPE,
        Toml.SECTION_FILES,
    }
    assert all(
        issue.level is DiagnosticLevel.INFO
        for issue in empty_parsed.validation_issues
        if issue.code is TomlDiagnosticCode.MISSING_SECTION
    )


# --- File-based TOML validation helpers ---


@pytest.mark.toml
@pytest.mark.parametrize(
    "filename",
    ["topmark.toml", "pyproject.toml"],
)
def test_unknown_keys_reported_via_from_toml_file(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    filename: str,
) -> None:
    """Unknown keys are also reported when loading from a split-parsed TOML source."""
    caplog.set_level("WARNING")
    p: Path = tmp_path / filename

    if filename == "topmark.toml":
        # Root table for topmark.toml
        p.write_text(
            """
            [files]
            include_patterns = ["src/**/*.py"]
            unknown_key = true
            """.lstrip(),
            encoding="utf-8",
        )
    else:
        # Nested under [tool.topmark] for pyproject.toml
        p.write_text(
            """
            [tool.topmark.files]
            include_patterns = ["src/**/*.py"]
            unknown_key = true
            """.lstrip(),
            encoding="utf-8",
        )

    draft: MutableConfig = draft_from_topmark_toml_file(p)

    # We should see a warning for the unknown key inside [files]
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f'Unknown key "unknown_key" in [{Toml.SECTION_FILES}]',
    )


@pytest.mark.toml
def test_unknown_key_in_config_section_warns_via_from_toml_file(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown keys in `[config]` are reported when loading from a TOML file."""
    caplog.set_level("WARNING")
    path: Path = tmp_path / "topmark.toml"
    write_toml_document(
        path=path,
        content="""
            [config]
            strict_config_checking = true
            bogus = 1
        """,
    )

    draft: MutableConfig = draft_from_topmark_toml_file(path)
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle='Unknown key "bogus" in [config]',
    )


@pytest.mark.toml
def test_unknown_key_in_writer_section_warns_via_from_toml_file(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown keys in `[writer]` are reported when loading from a TOML file."""
    caplog.set_level("WARNING")
    path: Path = tmp_path / "topmark.toml"
    write_toml_document(
        path=path,
        content="""
            [writer]
            strategy = "file"
            bogus = true
        """,
    )

    draft: MutableConfig = draft_from_topmark_toml_file(path)
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle='Unknown key "bogus" in [writer]',
    )
