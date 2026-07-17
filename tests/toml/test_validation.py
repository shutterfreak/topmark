# topmark:header:start
#
#   project      : TopMark
#   file         : test_validation.py
#   file_relpath : tests/toml/test_validation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for structured TOML validation issue adaptation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config.resolution.bridge import build_mutable_config_from_resolved_toml_sources
from topmark.diagnostic.model import DiagnosticLevel
from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.toml.keys import Toml
from topmark.toml.parse import parse_topmark_toml_table
from topmark.toml.resolution import ResolvedTopmarkTomlSource
from topmark.toml.resolution import ResolvedTopmarkTomlSources
from topmark.toml.validation import TomlDiagnosticCode
from topmark.toml.validation import TomlValidationIssue
from topmark.toml.validation import add_toml_issues

if TYPE_CHECKING:
    from collections.abc import Iterator

    from topmark.config.model import MutableConfig
    from topmark.toml.parse import ParsedTopmarkToml


def _issue(level: DiagnosticLevel, message: str) -> TomlValidationIssue:
    return TomlValidationIssue(
        code=TomlDiagnosticCode.UNKNOWN_SECTION_KEY,
        level=level,
        message=message,
        path=(Toml.SECTION_CONFIG, "bogus"),
        section=Toml.SECTION_CONFIG,
        key="bogus",
        allowed_keys=(Toml.KEY_ROOT, Toml.KEY_STRICT),
        suggestion=Toml.KEY_ROOT,
    )


def test_diagnostic_code_values_are_stable() -> None:
    """Machine-facing TOML diagnostic code values remain stable."""
    assert {code.value for code in TomlDiagnosticCode} == {
        "toml.unknown_top_level_section",
        "toml.unknown_top_level_key",
        "toml.missing_section",
        "toml.unknown_section_key",
        "toml.invalid_section_type",
        "toml.invalid_nested_section_type",
        "toml.dump_only_key_in_input",
    }


def test_issue_metadata_and_all_valid_levels_route_in_order_with_duplicates() -> None:
    """The adapter preserves metadata upstream and routes messages in supplied order."""
    issues: tuple[TomlValidationIssue, ...] = (
        _issue(DiagnosticLevel.INFO, "info"),
        _issue(DiagnosticLevel.WARNING, "duplicate"),
        _issue(DiagnosticLevel.WARNING, "duplicate"),
        _issue(DiagnosticLevel.ERROR, "error"),
    )
    log = MutableDiagnosticLog()

    add_toml_issues(log, issues)

    assert [(item.level, item.message) for item in log.items] == [
        (DiagnosticLevel.INFO, "info"),
        (DiagnosticLevel.WARNING, "duplicate"),
        (DiagnosticLevel.WARNING, "duplicate"),
        (DiagnosticLevel.ERROR, "error"),
    ]
    assert issues[1].path == (Toml.SECTION_CONFIG, "bogus")
    assert issues[1].section == Toml.SECTION_CONFIG
    assert issues[1].key == "bogus"
    assert issues[1].allowed_keys == (Toml.KEY_ROOT, Toml.KEY_STRICT)
    assert issues[1].suggestion == Toml.KEY_ROOT


def test_generator_is_consumed_once_and_empty_iterable_is_noop() -> None:
    """One-shot inputs work without pre-consumption; empty inputs change nothing."""
    iterations: list[str] = []

    def issue_generator() -> Iterator[TomlValidationIssue]:
        iterations.append("started")
        yield _issue(DiagnosticLevel.WARNING, "warning")

    log = MutableDiagnosticLog()
    generator: Iterator[TomlValidationIssue] = issue_generator()

    add_toml_issues(log, generator)
    add_toml_issues(log, ())

    assert iterations == ["started"]
    assert [(item.level, item.message) for item in log.items] == [
        (DiagnosticLevel.WARNING, "warning")
    ]
    assert list(generator) == []


def test_issues_survive_split_parsing_and_resolution_bridge() -> None:
    """Structured issues reach the merged draft's TOML-source diagnostic log."""
    issues: tuple[TomlValidationIssue, ...] = (
        _issue(DiagnosticLevel.INFO, "info"),
        _issue(DiagnosticLevel.WARNING, "warning"),
        _issue(DiagnosticLevel.ERROR, "error"),
    )
    parsed: ParsedTopmarkToml = parse_topmark_toml_table({}, validation_issues=issues)
    source = ResolvedTopmarkTomlSource(
        path=Path("topmark.toml"),
        parsed=parsed,
        kind="explicit",
        validation_issues=parsed.validation_issues,
        load_diagnostics=MutableDiagnosticLog().freeze(),
    )
    resolved = ResolvedTopmarkTomlSources(
        sources=[source],
        writer_options=None,
        strict=None,
        discovery_anchor=None,
    )

    draft: MutableConfig = build_mutable_config_from_resolved_toml_sources(resolved)

    assert parsed.validation_issues is issues
    assert [(item.level, item.message) for item in draft.validation_logs.toml_source.items] == [
        (DiagnosticLevel.INFO, "info"),
        (DiagnosticLevel.WARNING, "warning"),
        (DiagnosticLevel.ERROR, "error"),
    ]
