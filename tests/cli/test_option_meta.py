# topmark:header:start
#
#   project      : TopMark
#   file         : test_option_meta.py
#   file_relpath : tests/cli/test_option_meta.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for CLI option metadata helpers."""

from __future__ import annotations

from topmark.cli.keys import CliOpt
from topmark.cli.option_meta import CLI_HIDDEN_ALIAS_TARGETS
from topmark.cli.option_meta import CLI_OPTION_META_BY_LONG
from topmark.cli.option_meta import CliOptionMeta
from topmark.cli.option_meta import format_option_label
from topmark.cli.option_meta import format_option_labels


def test_format_option_label_returns_long_option_for_unknown_option() -> None:
    """Unknown options should render unchanged."""
    assert format_option_label("--unknown") == "--unknown"


def test_format_option_label_includes_known_short_alias() -> None:
    """Known options with short aliases should render both spellings."""
    assert format_option_label(CliOpt.VERBOSE) == "--verbose (-v)"


def test_cli_option_meta_label_omits_missing_short_alias() -> None:
    """Option metadata without a short alias should render the long spelling only."""
    assert CliOptionMeta(long="--example").label() == "--example"


def test_format_option_label_resolves_hidden_alias_to_canonical_label() -> None:
    """Hidden compatibility aliases should render using the canonical option."""
    assert format_option_label(CliOpt.INCLUDE_FILE_TYPE) == ("--include-file-types (-t)")


def test_format_option_labels_preserves_order() -> None:
    """Multiple option labels should render in the original order."""
    assert format_option_labels(
        [
            CliOpt.QUIET,
            "--unknown",
            CliOpt.INCLUDE_FILE_TYPE,
        ]
    ) == [
        "--quiet (-q)",
        "--unknown",
        "--include-file-types (-t)",
    ]


def test_hidden_alias_targets_map_aliases_to_canonical_options() -> None:
    """Hidden alias lookup should point to canonical long option spellings."""
    assert CLI_HIDDEN_ALIAS_TARGETS == {
        CliOpt.INCLUDE_FILE_TYPE: CliOpt.INCLUDE_FILE_TYPES,
        CliOpt.EXCLUDE_FILE_TYPE: CliOpt.EXCLUDE_FILE_TYPES,
    }


def test_cli_option_meta_registry_contains_expected_known_options() -> None:
    """Known metadata registry should expose stable canonical option keys."""
    assert set(CLI_OPTION_META_BY_LONG) >= {
        CliOpt.INCLUDE_FILE_TYPES,
        CliOpt.EXCLUDE_FILE_TYPES,
        CliOpt.VERBOSE,
        CliOpt.QUIET,
    }
