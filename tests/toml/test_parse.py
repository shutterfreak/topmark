# topmark:header:start
#
#   project      : TopMark
#   file         : test_parse.py
#   file_relpath : tests/toml/test_parse.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for pure split parsing of normalized TopMark TOML."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.config.types import FileWriteStrategy
from topmark.diagnostic.model import DiagnosticLevel
from topmark.toml.keys import Toml
from topmark.toml.parse import parse_topmark_toml_table
from topmark.toml.validation import TomlDiagnosticCode
from topmark.toml.validation import TomlValidationIssue

if TYPE_CHECKING:
    from topmark.toml.parse import ParsedTopmarkToml
    from topmark.toml.types import TomlTable
    from topmark.toml.types import TomlValue


@pytest.mark.parametrize("value", [True, False])
def test_config_booleans_preserve_false_without_entering_layered_config(
    value: bool,
) -> None:
    """Real booleans remain source-local and are never truthiness-coerced."""
    source: TomlTable = {
        Toml.SECTION_CONFIG: {
            Toml.KEY_STRICT: value,
            Toml.KEY_ROOT: value,
        },
        Toml.SECTION_FILES: {Toml.KEY_INCLUDE_PATTERNS: ["src/**"]},
    }

    parsed: ParsedTopmarkToml = parse_topmark_toml_table(source, validation_issues=())

    assert parsed.config_loading_options.strict is value
    assert parsed.source_options.root is value
    assert Toml.SECTION_CONFIG not in parsed.layered_config
    assert parsed.toml_fragment[Toml.SECTION_CONFIG] == source[Toml.SECTION_CONFIG]


@pytest.mark.parametrize("config", [None, "strict", [True], {"strict": "true", "root": 1}])
def test_missing_or_malformed_config_produces_unset_options(
    config: TomlValue | None,
) -> None:
    """The pure parser defensively ignores missing, malformed, and mistyped config."""
    source: TomlTable = {} if config is None else {Toml.SECTION_CONFIG: config}

    parsed: ParsedTopmarkToml = parse_topmark_toml_table(source, validation_issues=())

    assert parsed.config_loading_options.strict is None
    assert parsed.source_options.root is None
    if isinstance(config, dict):
        assert parsed.toml_fragment[Toml.SECTION_CONFIG] == config
    else:
        assert Toml.SECTION_CONFIG not in parsed.toml_fragment


@pytest.mark.parametrize("strategy", list(FileWriteStrategy))
def test_every_persisted_writer_strategy_is_parsed(
    strategy: FileWriteStrategy,
) -> None:
    """Every supported persisted writer strategy produces a source-local override."""
    source: TomlTable = {
        Toml.SECTION_WRITER: {
            Toml.KEY_STRATEGY: strategy.value,
        }
    }

    parsed: ParsedTopmarkToml = parse_topmark_toml_table(source, validation_issues=())

    assert parsed.writer_options is not None
    assert parsed.writer_options.file_write_strategy is strategy
    assert parsed.layered_config == {}
    assert parsed.toml_fragment == source


@pytest.mark.parametrize("strategy", [None, 1, "", "unknown"])
def test_invalid_persisted_writer_strategy_produces_no_override(
    strategy: TomlValue | None,
) -> None:
    """Missing, non-string, empty, and unknown strategies are ignored."""
    writer: TomlTable = {} if strategy is None else {Toml.KEY_STRATEGY: strategy}
    source: TomlTable = {Toml.SECTION_WRITER: writer}

    parsed: ParsedTopmarkToml = parse_topmark_toml_table(source, validation_issues=())

    assert parsed.writer_options is None
    assert parsed.toml_fragment == source


@pytest.mark.parametrize("writer", ["atomic", ["atomic"]])
def test_malformed_writer_table_is_ignored(writer: TomlValue) -> None:
    """Schema-owned writer shape failures are not promoted by the parser."""
    parsed: ParsedTopmarkToml = parse_topmark_toml_table(
        {Toml.SECTION_WRITER: writer},
        validation_issues=(),
    )

    assert parsed.writer_options is None
    assert parsed.toml_fragment == {}


def test_split_ownership_filters_unknown_and_malformed_top_level_sections() -> None:
    """Layered and full fragments retain only well-formed owned sections."""
    source: TomlTable = {
        Toml.SECTION_CONFIG: {Toml.KEY_ROOT: False},
        Toml.SECTION_HEADER: "malformed",
        Toml.SECTION_FIELDS: {"author": "Ada", "nested": {"company": "ACME"}},
        Toml.SECTION_FILES: {Toml.KEY_INCLUDE_PATTERNS: ["src/**"]},
        Toml.SECTION_WRITER: {Toml.KEY_STRATEGY: "atomic"},
        "unknown": {"promote": False},
    }

    parsed: ParsedTopmarkToml = parse_topmark_toml_table(source, validation_issues=())

    assert parsed.layered_config == {
        Toml.SECTION_FIELDS: source[Toml.SECTION_FIELDS],
        Toml.SECTION_FILES: source[Toml.SECTION_FILES],
    }
    assert parsed.toml_fragment == {
        Toml.SECTION_CONFIG: source[Toml.SECTION_CONFIG],
        Toml.SECTION_FIELDS: source[Toml.SECTION_FIELDS],
        Toml.SECTION_FILES: source[Toml.SECTION_FILES],
        Toml.SECTION_WRITER: source[Toml.SECTION_WRITER],
    }
    assert parsed.layered_config[Toml.SECTION_FIELDS] is not source[Toml.SECTION_FIELDS]
    assert parsed.toml_fragment[Toml.SECTION_FIELDS] is not source[Toml.SECTION_FIELDS]
    fields = parsed.layered_config[Toml.SECTION_FIELDS]
    source_fields = source[Toml.SECTION_FIELDS]
    assert isinstance(fields, dict)
    assert isinstance(source_fields, dict)
    assert fields["nested"] is source_fields["nested"]


def test_validation_issue_tuple_is_retained_and_empty_parse_is_stable() -> None:
    """Parsing is deterministic and retains the caller's exact issue tuple."""
    issues: tuple[TomlValidationIssue] = (
        TomlValidationIssue(
            code=TomlDiagnosticCode.MISSING_SECTION,
            level=DiagnosticLevel.INFO,
            message="missing",
            path=(Toml.SECTION_FILES,),
            section=Toml.SECTION_FILES,
        ),
    )

    first: ParsedTopmarkToml = parse_topmark_toml_table({}, validation_issues=issues)
    second: ParsedTopmarkToml = parse_topmark_toml_table({}, validation_issues=issues)

    assert first == second
    assert first.validation_issues is issues
    assert first.layered_config == {}
    assert first.toml_fragment == {}
