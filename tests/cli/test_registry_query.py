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
from tests.cli.conftest import assert_rich_output_no_such_option
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import parse_ndjson_records
from tests.helpers.ndjson import record_payload
from topmark.cli.cli_types import RegistryQueryParam
from topmark.cli.cli_types import RegistryRegexParam
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.keys import CliShortOpt
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
        ("never,opt-in", ["topmark:json"]),
        ("default,opt-in", []),
    ],
)
def test_registry_filetype_activation_and_identity_selection_are_intersected(
    activation: str,
    expected_keys: list[str],
) -> None:
    """Activation unions restrict, rather than broaden, identity selection."""
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
    ("activation_args", "expected_activations"),
    [
        pytest.param(
            (CliOpt.ACTIVATION, "never", CliOpt.ACTIVATION, "opt-in"),
            {"never", "opt-in"},
            id="repeated",
        ),
        pytest.param(
            (CliOpt.ACTIVATION, "never,opt-in"),
            {"never", "opt-in"},
            id="comma-separated",
        ),
        pytest.param(
            (CliShortOpt.ACTIVATION, "never,opt-in,never"),
            {"never", "opt-in"},
            id="short-comma-separated-duplicates",
        ),
    ],
)
@pytest.mark.parametrize(
    "subcommand",
    [
        CliCmd.REGISTRY_FILETYPES,
        CliCmd.REGISTRY_BINDINGS,
    ],
)
def test_registry_activation_values_compose_with_or_semantics(
    activation_args: tuple[str, ...],
    expected_activations: set[str],
    subcommand: str,
) -> None:
    """Repeated and comma-separated activation values form one deduplicated union."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            subcommand,
            *activation_args,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ],
    )

    assert_SUCCESS(result)
    payload: dict[str, object] = parse_json_object(result.output)
    if subcommand == CliCmd.REGISTRY_FILETYPES:
        entries: object = payload["filetypes"]
    else:
        entries = payload["bindings"]
    assert is_any_list(entries)
    assert entries
    assert {str(as_object_dict(entry)["activation"]) for entry in entries} <= expected_activations


@pytest.mark.parametrize(
    "output_format",
    [
        "text",
        "json",
        "ndjson",
    ],
)
@pytest.mark.parametrize(
    "subcommand",
    [
        CliCmd.REGISTRY_FILETYPES,
        CliCmd.REGISTRY_BINDINGS,
    ],
)
def test_registry_activation_filter_applies_to_text_and_machine_formats(
    output_format: str,
    subcommand: str,
) -> None:
    """Activation unions retain matching entries in every supported output format."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            subcommand,
            CliOpt.ACTIVATION,
            "never,opt-in",
            CliOpt.OUTPUT_FORMAT,
            output_format,
        ],
    )

    assert_SUCCESS(result)
    assert "topmark:json-as-jsonc" in result.output
    assert "topmark:markdown" not in result.output


@pytest.mark.parametrize(
    "subcommand",
    [
        CliCmd.REGISTRY_FILETYPES,
        CliCmd.REGISTRY_BINDINGS,
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        "never,",
        ",never",
        "never,,opt-in",
        "unknown",
    ],
)
def test_registry_activation_rejects_empty_segments_and_unknown_values(
    subcommand: str,
    value: str,
) -> None:
    """Malformed activation lists fail with Click's usage-error exit code."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            subcommand,
            CliOpt.ACTIVATION,
            value,
        ],
    )

    assert result.exit_code == CLICK_USAGE_ERROR_EXIT_CODE
    if "unknown" in value:
        assert "Invalid value 'unknown'" in result.output


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


def _binding_entries(result: Result) -> list[dict[str, object]]:
    """Return brief binding entries from a successful bindings JSON result."""
    payload: dict[str, object] = parse_json_object(result.output)
    entries: object = payload["bindings"]
    assert is_any_list(entries)
    return [as_object_dict(entry) for entry in entries]


@pytest.mark.parametrize(
    "query",
    [
        "json-as-jsonc",
        "topmark:json-as-jsonc",
        "*json*",
    ],
)
def test_registry_binding_queries_match_filetype_identity_forms(
    query: str,
) -> None:
    """Binding queries retain relationships whose file-type endpoint matches."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            CliOpt.OUTPUT_FORMAT,
            "json",
            query,
        ],
    )

    assert_SUCCESS(result)
    entries: list[dict[str, object]] = _binding_entries(result)
    assert entries
    assert all("json" in str(entry["file_type_key"]) for entry in entries)


def test_registry_binding_query_matches_processor_identity() -> None:
    """A binding query also selects relationships by processor endpoint identity."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            CliOpt.OUTPUT_FORMAT,
            "json",
            "slash",
        ],
    )

    assert_SUCCESS(result)
    entries: list[dict[str, object]] = _binding_entries(result)
    assert entries
    assert {entry["processor_key"] for entry in entries} == {"topmark:slash"}


def test_registry_binding_queries_and_regexes_are_endpoint_or_predicates() -> None:
    """Repeated queries and full-identity regexes form one endpoint-match union."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            CliOpt.MATCH_REGEX,
            "topmark:slash",
            CliOpt.OUTPUT_FORMAT,
            "json",
            "markdown",
            "json",
        ],
    )

    assert_SUCCESS(result)
    entries: list[dict[str, object]] = _binding_entries(result)
    assert entries
    assert all(
        str(entry["file_type_key"]) in {"topmark:markdown", "topmark:json"}
        or entry["processor_key"] == "topmark:slash"
        for entry in entries
    )


def test_registry_binding_activation_restricts_endpoint_queries() -> None:
    """Activation remains an AND filter on the file-type endpoint."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            CliOpt.ACTIVATION,
            "default",
            CliOpt.OUTPUT_FORMAT,
            "json",
            ":json-as-jsonc",
        ],
    )

    assert_SUCCESS(result)
    assert _binding_entries(result) == []


@pytest.mark.parametrize(
    "output_format",
    [
        "text",
        "markdown",
        "json",
        "ndjson",
    ],
)
def test_registry_binding_query_filters_all_output_formats(
    output_format: str,
) -> None:
    """Endpoint filtering is applied before every binding renderer."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            CliOpt.OUTPUT_FORMAT,
            output_format,
            ":json-as-jsonc",
        ],
    )

    assert_SUCCESS(result)
    assert "topmark:json-as-jsonc" in result.output
    assert "topmark:python" not in result.output


def test_registry_binding_query_empty_result_projects_every_section() -> None:
    """An unmatched binding query succeeds with empty machine-format sections."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            CliOpt.OUTPUT_FORMAT,
            "json",
            "missing:nope",
        ],
    )

    assert_SUCCESS(result)
    payload: dict[str, object] = parse_json_object(result.output)
    assert payload["bindings"] == []
    assert payload["unbound_filetypes"] == []
    assert payload["unused_processors"] == []


@pytest.mark.parametrize(
    "output_format",
    [
        "text",
        "markdown",
        "json",
        "ndjson",
    ],
)
def test_registry_binding_query_empty_result_succeeds_in_every_output_format(
    output_format: str,
) -> None:
    """An unmatched query produces the appropriate empty view in every format."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            CliOpt.OUTPUT_FORMAT,
            output_format,
            "missing:nope",
        ],
    )

    assert_SUCCESS(result)
    if output_format == "json":
        payload: dict[str, object] = parse_json_object(result.output)
        assert payload["bindings"] == []
        assert payload["unbound_filetypes"] == []
        assert payload["unused_processors"] == []
    elif output_format == "ndjson":
        assert parse_ndjson_records(result.output) == []
    else:
        assert "topmark:json-as-jsonc" not in result.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("too:many:separators",), "at most one ':'"),
        ((CliOpt.MATCH_REGEX, "("), "Invalid regular expression"),
    ],
)
def test_registry_binding_query_rejects_malformed_syntax(
    args: tuple[str, ...],
    message: str,
) -> None:
    """Binding query syntax uses Click's parser-error exit code."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            *args,
        ]
    )

    assert result.exit_code == CLICK_USAGE_ERROR_EXIT_CODE
    assert message in result.output


def test_registry_binding_query_rejects_an_empty_positional_value() -> None:
    """An empty binding query is rejected during Click parameter parsing."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            "",
        ],
    )

    assert result.exit_code == CLICK_USAGE_ERROR_EXIT_CODE
    assert "Usage: cli registry bindings" in result.output


def test_registry_binding_query_does_not_support_builtin_scope() -> None:
    """Bindings reject the ambiguous single-identity built-in scope option."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            CliOpt.REGISTRY_BUILTIN,
        ],
    )

    assert_rich_output_no_such_option(result, option_name=CliOpt.REGISTRY_BUILTIN)
