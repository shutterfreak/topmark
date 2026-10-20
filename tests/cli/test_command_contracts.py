# topmark:header:start
#
#   project      : TopMark
#   file         : test_command_contracts.py
#   file_relpath : tests/cli/test_command_contracts.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Metadata-driven compatibility contracts for the public CLI surface.

Click remains the source of truth for parser details.  The compact inventory in
this module records only the user-facing command paths and option applicability
that Click cannot distinguish from an intentional implementation change.
Focused command, renderer, machine-output, and exit-code tests cover behavior.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING
from typing import Final
from typing import Protocol
from typing import cast

import click
import pytest
import rich_click

from tests.cli.conftest import assert_rich_output_no_such_option
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import normalize_rich_cli_output
from tests.cli.conftest import run_cli
from tests.helpers.json import parse_json_object
from tests.helpers.machine import assert_machine_meta
from tests.helpers.ndjson import parse_ndjson_records
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.main import cli
from topmark.core.formats import OutputFormat
from topmark.core.machine.schemas import MachineKey
from topmark.pipeline.reporting import ReportScope

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping

    from click.testing import Result


CommandPath = tuple[str, ...]


class _RichOptionPanel(Protocol):
    """Minimal Rich Click option-panel metadata used by this contract test."""

    options: list[str]


DISPLAY_OPTIONS: Final[frozenset[str]] = frozenset(
    {CliOpt.COLOR_MODE, CliOpt.NO_COLOR_MODE, CliOpt.VERBOSE}
)
QUIET_OPTION: Final[frozenset[str]] = frozenset({CliOpt.QUIET})
OUTPUT_OPTION: Final[frozenset[str]] = frozenset({CliOpt.OUTPUT_FORMAT})
CONFIG_RESOLUTION_OPTIONS: Final[frozenset[str]] = frozenset(
    {CliOpt.CONFIG_FILES, CliOpt.NO_CONFIG}
)
PATH_INPUT_OPTIONS: Final[frozenset[str]] = frozenset(
    {CliOpt.STDIN_FILENAME, CliOpt.FILES_FROM, CliOpt.INCLUDE_FROM, CliOpt.EXCLUDE_FROM}
)
FILE_FILTER_OPTIONS: Final[frozenset[str]] = frozenset(
    {CliOpt.INCLUDE_PATTERNS, CliOpt.EXCLUDE_PATTERNS}
)
FILE_TYPE_FILTER_OPTIONS: Final[frozenset[str]] = frozenset(
    {CliOpt.OPT_IN_FILE_TYPE, CliOpt.INCLUDE_FILE_TYPES, CliOpt.EXCLUDE_FILE_TYPES}
)
HEADER_FORMATTING_OPTIONS: Final[frozenset[str]] = frozenset(
    {CliOpt.ALIGN_FIELDS, CliOpt.RELATIVE_TO}
)
CHECK_POLICY_OPTIONS: Final[frozenset[str]] = frozenset(
    {
        CliOpt.POLICY_HEADER_MUTATION_MODE,
        CliOpt.POLICY_ALLOW_HEADER_IN_EMPTY_FILES,
        CliOpt.POLICY_EMPTY_INSERT_MODE,
        CliOpt.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS,
        CliOpt.POLICY_ALLOW_REFLOW,
    }
)
SHARED_POLICY_OPTIONS: Final[frozenset[str]] = frozenset({CliOpt.POLICY_ALLOW_CONTENT_PROBE})
REMEDIATION_POLICY_OPTIONS: Final[frozenset[str]] = frozenset(
    {CliOpt.POLICY_BOM_BEFORE_SHEBANG, CliOpt.POLICY_MIXED_LINE_ENDINGS}
)
PIPELINE_REPORTING_OPTIONS: Final[frozenset[str]] = frozenset(
    {
        CliOpt.APPLY_CHANGES,
        CliOpt.WRITE_MODE,
        CliOpt.RENDER_DIFF,
        CliOpt.RESULTS_SUMMARY_MODE,
        CliOpt.REPORT,
    }
)
CONFIG_TEMPLATE_OPTIONS: Final[frozenset[str]] = frozenset(
    {CliOpt.CONFIG_FOR_PYPROJECT, CliOpt.CONFIG_ROOT}
)
REGISTRY_OPTIONS: Final[frozenset[str]] = frozenset({CliOpt.SHOW_DETAILS})
REGISTRY_ACTIVATION_OPTION: Final[frozenset[str]] = frozenset({CliOpt.ACTIVATION})
REGISTRY_IDENTITY_FILTERING_OPTIONS: Final[frozenset[str]] = frozenset(
    {CliOpt.MATCH_REGEX, CliOpt.REGISTRY_BUILTIN},
)


PUBLIC_COMMAND_OPTIONS: Final[Mapping[CommandPath, frozenset[str]]] = MappingProxyType(
    {
        (CliCmd.CONFIG,): frozenset(),
        (CliCmd.CONFIG, CliCmd.CONFIG_CHECK): (
            DISPLAY_OPTIONS
            | QUIET_OPTION
            | CONFIG_RESOLUTION_OPTIONS
            | {CliOpt.STRICT}
            | OUTPUT_OPTION
        ),
        (CliCmd.CONFIG, CliCmd.CONFIG_DEFAULTS): (
            DISPLAY_OPTIONS | CONFIG_TEMPLATE_OPTIONS | OUTPUT_OPTION
        ),
        (CliCmd.CONFIG, CliCmd.CONFIG_DUMP): (
            DISPLAY_OPTIONS
            | QUIET_OPTION
            | CONFIG_RESOLUTION_OPTIONS
            | {CliOpt.SHOW_CONFIG_LAYERS, CliOpt.FILES_FROM}
            | (PATH_INPUT_OPTIONS - {CliOpt.STDIN_FILENAME, CliOpt.FILES_FROM})
            | FILE_FILTER_OPTIONS
            | FILE_TYPE_FILTER_OPTIONS
            | HEADER_FORMATTING_OPTIONS
            | OUTPUT_OPTION
        ),
        (CliCmd.CONFIG, CliCmd.CONFIG_INIT): (
            DISPLAY_OPTIONS | CONFIG_TEMPLATE_OPTIONS | OUTPUT_OPTION
        ),
        (CliCmd.PROBE,): (
            DISPLAY_OPTIONS
            | QUIET_OPTION
            | {CliOpt.STRICT}
            | CONFIG_RESOLUTION_OPTIONS
            | PATH_INPUT_OPTIONS
            | FILE_FILTER_OPTIONS
            | FILE_TYPE_FILTER_OPTIONS
            | SHARED_POLICY_OPTIONS
            | OUTPUT_OPTION
        ),
        (CliCmd.CHECK,): (
            DISPLAY_OPTIONS
            | QUIET_OPTION
            | {CliOpt.STRICT}
            | CONFIG_RESOLUTION_OPTIONS
            | PATH_INPUT_OPTIONS
            | FILE_FILTER_OPTIONS
            | FILE_TYPE_FILTER_OPTIONS
            | HEADER_FORMATTING_OPTIONS
            | CHECK_POLICY_OPTIONS
            | SHARED_POLICY_OPTIONS
            | REMEDIATION_POLICY_OPTIONS
            | PIPELINE_REPORTING_OPTIONS
            | OUTPUT_OPTION
        ),
        (CliCmd.STRIP,): (
            DISPLAY_OPTIONS
            | QUIET_OPTION
            | {CliOpt.STRICT}
            | CONFIG_RESOLUTION_OPTIONS
            | PATH_INPUT_OPTIONS
            | FILE_FILTER_OPTIONS
            | FILE_TYPE_FILTER_OPTIONS
            | SHARED_POLICY_OPTIONS
            | REMEDIATION_POLICY_OPTIONS
            | PIPELINE_REPORTING_OPTIONS
            | OUTPUT_OPTION
        ),
        (CliCmd.REGISTRY,): frozenset(),
        (CliCmd.REGISTRY, CliCmd.REGISTRY_FILETYPES): (
            DISPLAY_OPTIONS
            | REGISTRY_OPTIONS
            | REGISTRY_ACTIVATION_OPTION
            | REGISTRY_IDENTITY_FILTERING_OPTIONS
            | OUTPUT_OPTION
        ),
        (CliCmd.REGISTRY, CliCmd.REGISTRY_PROCESSORS): (
            DISPLAY_OPTIONS | REGISTRY_OPTIONS | REGISTRY_IDENTITY_FILTERING_OPTIONS | OUTPUT_OPTION
        ),
        (CliCmd.REGISTRY, CliCmd.REGISTRY_BINDINGS): (
            DISPLAY_OPTIONS | REGISTRY_OPTIONS | REGISTRY_ACTIVATION_OPTION | OUTPUT_OPTION
        ),
        (CliCmd.VERSION,): DISPLAY_OPTIONS | {CliOpt.SEMVER_VERSION} | OUTPUT_OPTION,
    }
)
"""Public paths and canonical visible options; update deliberately with CLI changes."""


CSV_FILE_TYPE_OPTIONS: Final[frozenset[str]] = frozenset(
    {CliOpt.OPT_IN_FILE_TYPE, CliOpt.INCLUDE_FILE_TYPES, CliOpt.EXCLUDE_FILE_TYPES}
)
"""File-type filters whose repeatable values support comma-separated input."""


HIDDEN_ALIASES: Final[Mapping[str, str]] = MappingProxyType(
    {
        CliOpt.INCLUDE_FILE_TYPE: CliOpt.INCLUDE_FILE_TYPES,
        CliOpt.EXCLUDE_FILE_TYPE: CliOpt.EXCLUDE_FILE_TYPES,
    }
)
"""Compatibility aliases, keyed by hidden spelling and mapped to canonical spelling."""


COMMAND_SPECIFIC_HELP_OPTIONS: Final[frozenset[str]] = frozenset({CliOpt.FILES_FROM})
"""Shared parser options whose help describes command-specific behavior."""

OPTION_GROUPED_COMMAND_PATHS: Final[tuple[CommandPath, ...]] = (
    (CliCmd.CHECK,),
    (CliCmd.STRIP,),
    (CliCmd.PROBE,),
    (CliCmd.CONFIG, CliCmd.CONFIG_CHECK),
    (CliCmd.CONFIG, CliCmd.CONFIG_DEFAULTS),
    (CliCmd.CONFIG, CliCmd.CONFIG_DUMP),
    (CliCmd.CONFIG, CliCmd.CONFIG_INIT),
    (CliCmd.REGISTRY, CliCmd.REGISTRY_FILETYPES),
    (CliCmd.REGISTRY, CliCmd.REGISTRY_PROCESSORS),
    (CliCmd.REGISTRY, CliCmd.REGISTRY_BINDINGS),
    (CliCmd.VERSION,),
)
"""Commands whose complete option surfaces use explicit Rich Click panels."""


def _walk_commands(
    command: click.Command,
    path: CommandPath = (),
) -> Iterator[tuple[CommandPath, click.Command]]:
    """Yield a Click command tree including command groups.

    Args:
        command: Root command to traverse.
        path: Existing command path before ``command``.

    Yields:
        Public command path and its Click command object.
    """
    command_path: CommandPath = path + (command.name or "",)
    yield command_path, command
    if isinstance(command, click.Group):
        for child in command.commands.values():
            yield from _walk_commands(child, command_path)


def _command_for_path(path: CommandPath) -> click.Command:
    """Return the live Click command registered at a public command path."""
    command: click.Command = cli
    for name in path:
        assert isinstance(command, click.Group)
        child: click.Command | None = command.commands.get(name)
        assert child is not None, f"command path is not registered: {' '.join(path)}"
        command = child
    return command


def _visible_options(command: click.Command) -> list[click.Option]:
    """Return non-hidden option declarations in registration order."""
    return [
        param for param in command.params if isinstance(param, click.Option) and not param.hidden
    ]


def _panel_option_names(command: click.Command) -> list[str]:
    """Return option spellings assigned to explicit Rich Click panels."""
    assert isinstance(command, rich_click.RichCommand)
    return [
        option for panel in command.panels for option in cast("_RichOptionPanel", panel).options
    ]


def _option(command: click.Command, canonical: str) -> click.Option:
    """Return the unique visible option using a canonical long spelling."""
    matches: list[click.Option] = [
        option for option in _visible_options(command) if canonical in option.opts
    ]
    assert len(matches) == 1, f"expected one {canonical} option on {command.name}"
    return matches[0]


@pytest.mark.smoke
def test_click_registration_matches_public_command_inventory() -> None:
    """The public CLI inventory and the live nested Click tree agree exactly."""
    actual_paths: set[CommandPath] = {
        path[1:] for path, _command in _walk_commands(cli) if path[1:]
    }
    assert actual_paths == set(PUBLIC_COMMAND_OPTIONS)


@pytest.mark.smoke
@pytest.mark.parametrize("path", PUBLIC_COMMAND_OPTIONS, ids="-".join)
def test_command_exposes_exactly_its_declared_visible_options(path: CommandPath) -> None:
    """Each public command exposes precisely its declared public option set."""
    command: click.Command = _command_for_path(path)
    actual: set[str] = {
        option_name
        for option in _visible_options(command)
        for option_name in option.opts
        if option_name.startswith("--")
    }
    assert actual == set(PUBLIC_COMMAND_OPTIONS[path])


@pytest.mark.parametrize("path", OPTION_GROUPED_COMMAND_PATHS, ids="-".join)
def test_option_panels_cover_every_visible_option(
    path: CommandPath,
) -> None:
    """Every visible option belongs to one explicit help panel where panels are used."""
    command: click.Command = _command_for_path(path)
    panel_option_names: list[str] = _panel_option_names(command)
    expected_option_names: set[str] = set(PUBLIC_COMMAND_OPTIONS[path]) | {CliOpt.HELP}

    assert len(panel_option_names) == len(set(panel_option_names))
    assert set(panel_option_names) == expected_option_names


@pytest.mark.smoke
def test_shared_option_metadata_is_consistent_across_applicable_commands() -> None:
    """Common decorators retain option shape, aliases, defaults, and help metadata."""
    by_option: dict[str, list[click.Option]] = {}
    for path, expected_options in PUBLIC_COMMAND_OPTIONS.items():
        command: click.Command = _command_for_path(path)
        for canonical in expected_options:
            by_option.setdefault(canonical, []).append(_option(command, canonical))

    for canonical, options in by_option.items():
        first: click.Option = options[0]
        for option in options[1:]:
            assert option.name == first.name, canonical
            assert option.opts == first.opts, canonical
            assert option.secondary_opts == first.secondary_opts, canonical
            assert option.nargs == first.nargs, canonical
            assert option.multiple is first.multiple, canonical
            assert option.is_flag is first.is_flag, canonical
            assert option.count is first.count, canonical
            assert option.default == first.default, canonical
            assert type(option.type) is type(first.type), canonical
            if canonical not in COMMAND_SPECIFIC_HELP_OPTIONS:
                assert option.help == first.help, canonical

        assert first.help is not None, canonical

    for path, expected_options in PUBLIC_COMMAND_OPTIONS.items():
        command = _command_for_path(path)
        for canonical in expected_options:
            visible_option: click.Option = _option(command, canonical)
            if "-" in canonical[2:] and not visible_option.secondary_opts:
                trap: str = "--" + canonical[2:].replace("-", "_")
                assert any(
                    trap in option.opts and option.hidden
                    for option in command.params
                    if isinstance(option, click.Option)
                )

    assert _option(_command_for_path((CliCmd.CHECK,)), CliOpt.VERBOSE).count
    assert _option(_command_for_path((CliCmd.CHECK,)), CliOpt.VERBOSE).default == 0
    report_option: click.Option = _option(_command_for_path((CliCmd.CHECK,)), CliOpt.REPORT)
    assert report_option.default == ReportScope.ACTIONABLE

    for canonical in CSV_FILE_TYPE_OPTIONS:
        for command in (
            _command_for_path((CliCmd.CONFIG, CliCmd.CONFIG_DUMP)),
            _command_for_path((CliCmd.PROBE,)),
            _command_for_path((CliCmd.CHECK,)),
            _command_for_path((CliCmd.STRIP,)),
        ):
            option: click.Option = _option(command, canonical)
            assert option.multiple
            assert option.callback is not None

    for hidden_alias, canonical in HIDDEN_ALIASES.items():
        for path in (
            (CliCmd.CONFIG, CliCmd.CONFIG_DUMP),
            (CliCmd.PROBE,),
            (CliCmd.CHECK,),
            (CliCmd.STRIP,),
        ):
            command = _command_for_path(path)
            canonical_option: click.Option = _option(command, canonical)
            aliases: list[click.Option] = [
                option
                for option in command.params
                if isinstance(option, click.Option) and hidden_alias in option.opts
            ]
            assert len(aliases) == 1
            alias: click.Option = aliases[0]
            assert alias.hidden
            assert alias.name == canonical_option.name
            assert alias.multiple is canonical_option.multiple
            assert alias.callback is canonical_option.callback


@pytest.mark.parametrize(
    "path", [path for path, options in PUBLIC_COMMAND_OPTIONS.items() if options], ids="-".join
)
def test_help_exposes_public_options_and_hides_compatibility_aliases(path: CommandPath) -> None:
    """Help remains a projection of public option metadata, not parser internals."""
    result: Result = run_cli([*path, CliOpt.HELP])
    assert_SUCCESS(result)
    assert "Usage:" in normalize_rich_cli_output(result.output)
    context = click.Context(_command_for_path(path))
    for option in PUBLIC_COMMAND_OPTIONS[path]:
        record: tuple[str, str] | None = _option(context.command, option).get_help_record(context)
        assert record is not None
        assert option in record[0]
    for hidden_alias in HIDDEN_ALIASES:
        hidden_option: click.Option | None = next(
            (
                option
                for option in context.command.params
                if isinstance(option, click.Option) and hidden_alias in option.opts
            ),
            None,
        )
        if hidden_option is not None:
            assert hidden_option.get_help_record(context) is None


@pytest.mark.parametrize(
    "path", [path for path, options in PUBLIC_COMMAND_OPTIONS.items() if options], ids="-".join
)
def test_options_outside_a_command_applicability_set_are_rejected(path: CommandPath) -> None:
    """Every public option absent from a command is rejected by Click parsing."""
    all_options: frozenset[str] = frozenset(
        option for options in PUBLIC_COMMAND_OPTIONS.values() for option in options
    )
    for option in all_options - PUBLIC_COMMAND_OPTIONS[path]:
        result: Result = run_cli([*path, option])
        assert_rich_output_no_such_option(result, option_name=option)


@pytest.mark.parametrize(
    "path",
    [
        (CliCmd.VERSION,),
        (CliCmd.CONFIG, CliCmd.CONFIG_DEFAULTS),
        (CliCmd.REGISTRY, CliCmd.REGISTRY_FILETYPES),
    ],
    ids="-".join,
)
def test_machine_output_projections_retain_the_shared_envelope(path: CommandPath) -> None:
    """Metadata-declared machine options retain JSON and NDJSON envelope fields."""
    json_result: Result = run_cli([*path, CliOpt.OUTPUT_FORMAT, OutputFormat.JSON.value])
    assert_SUCCESS(json_result)
    json_payload: dict[str, object] = parse_json_object(json_result.output)
    assert_machine_meta(json_payload.get(MachineKey.META.value))

    ndjson_result: Result = run_cli([*path, CliOpt.OUTPUT_FORMAT, OutputFormat.NDJSON.value])
    assert_SUCCESS(ndjson_result)
    records: list[dict[str, object]] = parse_ndjson_records(ndjson_result.output)
    assert records
    for record in records:
        kind: object | None = record.get(MachineKey.KIND.value)
        assert isinstance(kind, str)
        assert_machine_meta(record.get(MachineKey.META.value), expected_detail_level="brief")
        assert kind in record
