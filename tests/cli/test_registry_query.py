# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_query.py
#   file_relpath : tests/cli/test_registry_query.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for compact registry identity queries."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import CLICK_USAGE_ERROR_EXIT_CODE
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import parse_ndjson_records
from tests.helpers.ndjson import record_payload
from topmark.cli.cli_types import RegistryQueryParam
from topmark.cli.cli_types import RegistryRegexParam
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.registry.query import RegistryIdentityQuery
from topmark.registry.query import RegistryRegex

if TYPE_CHECKING:
    from click.testing import Result


def _qualified_keys(
    result: Result,
    payload_key: str,
) -> list[str]:
    """Return qualified keys from a successful registry JSON result."""
    payload: dict[str, object] = parse_json_object(result.output)
    entries: object | None = payload.get(payload_key)
    assert is_any_list(entries)
    return [str(as_object_dict(entry)["qualified_key"]) for entry in entries]


def test_registry_query_parameter_types_preserve_already_parsed_values() -> None:
    """Click parameter conversion is idempotent for its typed selection values."""
    query: RegistryIdentityQuery = RegistryIdentityQuery.parse(":json")
    regex: RegistryRegex = RegistryRegex.parse("topmark:json")

    assert RegistryQueryParam().convert(query, None, None) is query
    assert RegistryRegexParam().convert(regex, None, None) is regex


@pytest.mark.parametrize(
    ("subcommand", "payload_key", "queries", "expected_keys"),
    [
        (
            CliCmd.REGISTRY_FILETYPES,
            "filetypes",
            (":json", ":python"),
            ("topmark:json", "topmark:python"),
        ),
        (
            CliCmd.REGISTRY_PROCESSORS,
            "processors",
            ("markdown", "xml"),
            ("topmark:markdown", "topmark:xml"),
        ),
    ],
)
def test_registry_queries_or_identity_predicates(
    subcommand: str,
    payload_key: str,
    queries: tuple[str, ...],
    expected_keys: tuple[str, ...],
) -> None:
    """Repeated positional queries select the union of their matches."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            subcommand,
            CliOpt.OUTPUT_FORMAT,
            "json",
            *queries,
        ],
    )

    assert_SUCCESS(result)
    assert _qualified_keys(result, payload_key) == list(expected_keys)


def test_registry_builtin_restricts_a_positional_query() -> None:
    """The built-in alias is a restrictive scope rather than an OR selector."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.REGISTRY_BUILTIN,
            CliOpt.OUTPUT_FORMAT,
            "json",
            ":json",
        ],
    )

    assert_SUCCESS(result)
    assert _qualified_keys(result, "filetypes") == ["topmark:json"]


@pytest.mark.parametrize(
    "output_format",
    [
        "text",
        "markdown",
        "json",
        "ndjson",
    ],
)
def test_registry_query_filters_every_output_format(
    output_format: str,
) -> None:
    """Identity selection is shared by every file type output format."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.OUTPUT_FORMAT,
            output_format,
            ":json",
        ],
    )

    assert_SUCCESS(result)
    assert "topmark:json" in result.output
    assert "topmark:python" not in result.output


@pytest.mark.parametrize(
    "output_format",
    [
        "json",
        "ndjson",
    ],
)
def test_registry_query_filters_machine_entries_without_changing_their_shape(
    output_format: str,
) -> None:
    """Machine formats serialize only selected entries with their usual identities."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.OUTPUT_FORMAT,
            output_format,
            ":json",
        ],
    )

    assert_SUCCESS(result)
    if output_format == "json":
        assert _qualified_keys(result, "filetypes") == ["topmark:json"]
        return

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert [record_payload(record)["qualified_key"] for record in records] == ["topmark:json"]


def test_registry_match_regex_is_an_alternative_identity_predicate() -> None:
    """Regex and positional queries are ORed against full qualified identities."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.MATCH_REGEX,
            "topmark:(json|toml)",
            CliOpt.OUTPUT_FORMAT,
            "json",
            ":python",
        ],
    )

    assert_SUCCESS(result)
    assert _qualified_keys(result, "filetypes") == [
        "topmark:json",
        "topmark:python",
        "topmark:toml",
    ]


@pytest.mark.parametrize(
    ("activation", "expected_keys"),
    [
        ("never", ["topmark:json"]),
        ("opt-in", []),
    ],
)
def test_registry_filetype_activation_and_identity_selection_are_intersected(
    activation: str,
    expected_keys: list[str],
) -> None:
    """Activation filtering restricts, rather than broadens, identity selection."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.ACTIVATION,
            activation,
            CliOpt.OUTPUT_FORMAT,
            "json",
            ":json",
        ],
    )

    assert_SUCCESS(result)
    assert _qualified_keys(result, "filetypes") == expected_keys


@pytest.mark.parametrize(
    ("subcommand", "payload_key"),
    [
        (CliCmd.REGISTRY_FILETYPES, "filetypes"),
        (CliCmd.REGISTRY_PROCESSORS, "processors"),
    ],
)
def test_registry_query_empty_results_are_successful(
    subcommand: str,
    payload_key: str,
) -> None:
    """An unmatched query emits a valid empty machine-readable result."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            subcommand,
            CliOpt.OUTPUT_FORMAT,
            "json",
            "missing:nope",
        ],
    )

    assert_SUCCESS(result)
    assert _qualified_keys(result, payload_key) == []


@pytest.mark.parametrize(
    ("subcommand", "query", "message"),
    [
        (CliCmd.REGISTRY_FILETYPES, "", "Registry query must"),
        (CliCmd.REGISTRY_PROCESSORS, "too:many:separators", "at most one ':'"),
    ],
)
def test_registry_query_rejects_malformed_identity_syntax(
    subcommand: str,
    query: str,
    message: str,
) -> None:
    """Malformed structured identity queries fail during Click parsing."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            subcommand,
            query,
        ],
    )

    assert result.exit_code == CLICK_USAGE_ERROR_EXIT_CODE
    assert message in result.output


@pytest.mark.parametrize(
    "subcommand",
    [
        CliCmd.REGISTRY_FILETYPES,
        CliCmd.REGISTRY_PROCESSORS,
    ],
)
def test_registry_match_regex_rejects_invalid_expressions(
    subcommand: str,
) -> None:
    """Invalid regular expressions are reported as CLI usage errors."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            subcommand,
            CliOpt.MATCH_REGEX,
            "(",
        ],
    )

    assert result.exit_code == CLICK_USAGE_ERROR_EXIT_CODE
    assert "Invalid regular expression" in result.output
