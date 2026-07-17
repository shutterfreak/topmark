# topmark:header:start
#
#   project      : TopMark
#   file         : test_loaders.py
#   file_relpath : tests/toml/test_loaders.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for filesystem and in-memory TopMark TOML loading."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import tomlkit

from topmark.toml import loaders
from topmark.toml.keys import Toml
from topmark.toml.loaders import load_topmark_toml_source
from topmark.toml.loaders import load_topmark_toml_table
from topmark.toml.schema import TomlValidationMode

if TYPE_CHECKING:
    from topmark.toml.parse import ParsedTopmarkToml
    from topmark.toml.types import TomlTable
    from topmark.toml.validation import TomlValidationIssue


def test_plain_source_loads_utf8_and_returns_independent_plain_tables(
    tmp_path: Path,
) -> None:
    """A plain source is UTF-8 decoded and each call returns independent state."""
    path: Path = tmp_path / "topmark.toml"
    path.write_text('[fields]\nauthor = "Ren\u00e9e"\n', encoding="utf-8")

    first: ParsedTopmarkToml | None = load_topmark_toml_source(path)
    second: ParsedTopmarkToml | None = load_topmark_toml_source(path)

    assert first is not None
    assert second is not None
    assert first.toml_fragment == {Toml.SECTION_FIELDS: {"author": "Ren\u00e9e"}}
    assert second.toml_fragment == first.toml_fragment
    assert second.toml_fragment is not first.toml_fragment
    assert second.toml_fragment[Toml.SECTION_FIELDS] is not first.toml_fragment[Toml.SECTION_FIELDS]


@pytest.mark.parametrize("content", ["", "# comment only\n"])
def test_empty_plain_source_is_a_valid_empty_topmark_source(
    tmp_path: Path,
    content: str,
) -> None:
    """Empty and comment-only documents parse with empty-source semantics."""
    path: Path = tmp_path / "topmark.toml"
    path.write_text(content, encoding="utf-8")

    parsed: ParsedTopmarkToml | None = load_topmark_toml_source(path)

    assert parsed is not None
    assert parsed.layered_config == {}
    assert parsed.toml_fragment == {}
    assert len(parsed.validation_issues) == 8


def test_pyproject_file_load_matches_direct_extraction(tmp_path: Path) -> None:
    """Canonical pyproject loading agrees with direct in-memory extraction."""
    path: Path = tmp_path / "pyproject.toml"
    path.write_text(
        """
[build-system]
requires = ["setuptools"]

[project]
name = "unrelated"

[tool.other]
enabled = true

[tool.topmark.config]
strict = false
root = true

[tool.topmark.fields]
author = "Ren\u00e9e"
""".lstrip(),
        encoding="utf-8",
    )

    from_file: ParsedTopmarkToml | None = load_topmark_toml_source(path)
    document: TomlTable = tomlkit.parse(path.read_text(encoding="utf-8")).unwrap()
    direct: ParsedTopmarkToml | None = load_topmark_toml_table(
        document,
        source_path=tmp_path / "different-context.toml",
        from_pyproject=True,
    )

    assert from_file is not None
    assert direct is not None
    assert from_file == direct
    assert from_file.config_loading_options.strict is False
    assert from_file.source_options.root is True
    assert not any(
        issue.path[0] in {"build-system", "project", "tool"}
        for issue in from_file.validation_issues
    )


def test_only_canonical_pyproject_filename_triggers_extraction(tmp_path: Path) -> None:
    """Filename classification is exact and case-sensitive."""
    path: Path = tmp_path / "PYPROJECT.toml"
    path.write_text("[tool.topmark.config]\nstrict = true\n", encoding="utf-8")

    parsed: ParsedTopmarkToml | None = load_topmark_toml_source(path)

    assert parsed is not None
    assert parsed.config_loading_options.strict is None
    assert parsed.toml_fragment == {}
    assert parsed.validation_issues[0].path == ("tool",)


@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_missing_files_and_directories_return_none(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    kind: str,
) -> None:
    """Ordinary filesystem read failures are conservative and path-qualified."""
    path: Path = tmp_path / "topmark.toml"
    if kind == "directory":
        path.mkdir()
    caplog.set_level("ERROR")

    assert load_topmark_toml_source(path) is None
    assert str(path) in caplog.text
    assert "Error loading TOML" in caplog.text


def test_other_oserror_at_read_boundary_returns_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Platform-dependent read errors use the same conservative load contract."""
    path: Path = tmp_path / "topmark.toml"

    def fail_read_text(self: Path, *, encoding: str) -> str:
        assert self == path
        assert encoding == "utf-8"
        raise OSError("simulated read failure")

    monkeypatch.setattr(Path, "read_text", fail_read_text)
    caplog.set_level("ERROR")

    assert load_topmark_toml_source(path) is None
    assert str(path) in caplog.text
    assert "Error loading TOML" in caplog.text


def test_invalid_utf8_is_reported_as_decoding_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Invalid UTF-8 never leaks and is not mislabeled as normalization."""
    path: Path = tmp_path / "topmark.toml"
    path.write_bytes(b"[config]\nstrict = \xff\n")
    caplog.set_level("ERROR")

    assert load_topmark_toml_source(path) is None
    assert str(path) in caplog.text
    assert "Error decoding TOML" in caplog.text
    assert "Error normalizing TOML" not in caplog.text


def test_malformed_toml_returns_none_without_leaking_parser_details(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Syntax failures return no partial source and use a broad parse category."""
    path: Path = tmp_path / "topmark.toml"
    path.write_text("[config\nstrict = true\n", encoding="utf-8")
    caplog.set_level("ERROR")

    assert load_topmark_toml_source(path) is None
    assert str(path) in caplog.text
    assert "Error parsing TOML" in caplog.text


def test_unsupported_toml_datetime_returns_none_as_normalization_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TOML values outside TopMark's normalized model fail conservatively."""
    path: Path = tmp_path / "topmark.toml"
    path.write_text("created = 2026-07-17T12:00:00Z\n", encoding="utf-8")
    caplog.set_level("ERROR")

    assert load_topmark_toml_source(path) is None
    assert str(path) in caplog.text
    assert "Error normalizing TOML" in caplog.text


def test_loader_validates_in_input_mode_and_preserves_issue_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Schema validation precedes splitting and its tuple is passed unchanged."""
    expected: tuple[TomlValidationIssue, ...] = ()
    calls: list[tuple[TomlTable, TomlValidationMode]] = []

    class SchemaSpy:
        def validate(
            self,
            table: TomlTable,
            *,
            mode: TomlValidationMode,
        ) -> tuple[TomlValidationIssue, ...]:
            calls.append((table, mode))
            return expected

    monkeypatch.setattr(loaders, "TOPMARK_TOML_SCHEMA", SchemaSpy())
    source: TomlTable = {Toml.SECTION_CONFIG: {Toml.KEY_STRICT: False}}

    parsed: ParsedTopmarkToml | None = load_topmark_toml_table(source)

    assert parsed is not None
    assert calls == [(source, TomlValidationMode.INPUT)]
    assert parsed.validation_issues is expected
