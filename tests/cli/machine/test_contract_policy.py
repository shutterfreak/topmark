# topmark:header:start
#
#   project      : TopMark
#   file         : test_contract_policy.py
#   file_relpath : tests/cli/machine/test_contract_policy.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Cross-command machine-output compatibility policy tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_SUCCESS_or_WOULD_CHANGE
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from tests.helpers.json import parse_json_object
from tests.helpers.machine import assert_machine_stdout_is_clean
from tests.helpers.machine import assert_ndjson_record_envelopes
from tests.helpers.ndjson import parse_ndjson_records
from topmark.cli.console.color import ColorMode
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.formats import OutputFormat
from topmark.core.machine.schemas import DetailLevel
from topmark.core.machine.schemas import MachineKey
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_mapping

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(
            [
                CliCmd.VERSION,
                CliOpt.OUTPUT_FORMAT,
                OutputFormat.JSON.value,
            ],
            id="version",
        ),
        pytest.param(
            [
                CliCmd.CONFIG,
                CliCmd.CONFIG_DEFAULTS,
                CliOpt.OUTPUT_FORMAT,
                OutputFormat.JSON.value,
            ],
            id="config-defaults",
        ),
        pytest.param(
            [
                CliCmd.REGISTRY,
                CliCmd.REGISTRY_FILETYPES,
                CliOpt.OUTPUT_FORMAT,
                OutputFormat.JSON.value,
            ],
            id="registry-filetypes",
        ),
    ],
)
def test_json_outputs_keep_baseline_meta_contract(args: list[str]) -> None:
    """Representative JSON commands should expose the documented baseline metadata."""
    result: Result = run_cli(args)
    assert_SUCCESS(result)
    assert_machine_stdout_is_clean(result.stdout)

    payload: dict[str, object] = parse_json_object(result.output)
    meta_obj: object | None = payload.get(MachineKey.META.value)
    assert is_mapping(meta_obj)

    meta: dict[str, object] = as_object_dict(meta_obj)
    assert isinstance(meta.get("tool"), str)
    assert isinstance(meta.get("version"), str)
    assert isinstance(meta.get("platform"), str)
    assert isinstance(meta.get("python_version"), str)
    assert isinstance(meta.get("machine"), str)


def test_processing_json_summary_keeps_baseline_meta_contract(tmp_path: Path) -> None:
    """Processing JSON summary output should expose the documented baseline metadata."""
    source: Path = tmp_path / "example.py"
    source.write_text('print("hello")\n', encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.RESULTS_SUMMARY_MODE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            source.name,
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)
    assert_machine_stdout_is_clean(result.stdout)

    payload: dict[str, object] = parse_json_object(result.output)
    meta_obj: object | None = payload.get(MachineKey.META.value)
    assert is_mapping(meta_obj)

    meta: dict[str, object] = as_object_dict(meta_obj)
    assert isinstance(meta.get("tool"), str)
    assert isinstance(meta.get("version"), str)
    assert isinstance(meta.get("platform"), str)
    assert isinstance(meta.get("python_version"), str)
    assert isinstance(meta.get("machine"), str)


@pytest.mark.parametrize(
    ("args", "output_format"),
    [
        pytest.param(
            [
                CliCmd.VERSION,
                CliOpt.OUTPUT_FORMAT,
                OutputFormat.JSON.value,
            ],
            OutputFormat.JSON,
            id="version-json",
        ),
        pytest.param(
            [
                CliCmd.CONFIG,
                CliCmd.CONFIG_DEFAULTS,
                CliOpt.OUTPUT_FORMAT,
                OutputFormat.NDJSON.value,
            ],
            OutputFormat.NDJSON,
            id="config-defaults-ndjson",
        ),
        pytest.param(
            [
                CliCmd.CONFIG,
                CliCmd.CONFIG_CHECK,
                CliOpt.OUTPUT_FORMAT,
                OutputFormat.JSON.value,
            ],
            OutputFormat.JSON,
            id="config-check-json",
        ),
        pytest.param(
            [
                CliCmd.REGISTRY,
                CliCmd.REGISTRY_FILETYPES,
                CliOpt.OUTPUT_FORMAT,
                OutputFormat.NDJSON.value,
            ],
            OutputFormat.NDJSON,
            id="registry-filetypes-ndjson",
        ),
    ],
)
def test_machine_output_ignores_forced_color_without_polluting_stdout(
    args: list[str],
    output_format: OutputFormat,
) -> None:
    """Forced color is warned on STDERR while machine STDOUT remains parseable."""
    result: Result = run_cli(
        [
            *args,
            CliOpt.COLOR_MODE,
            ColorMode.ALWAYS.value,
        ]
    )
    assert_SUCCESS(result)

    assert (
        f"{CliOpt.COLOR_MODE}={ColorMode.ALWAYS.value} "
        f"is ignored when {CliOpt.OUTPUT_FORMAT}={output_format.value}." in result.stderr
    )
    assert_machine_stdout_is_clean(result.stdout)
    if output_format is OutputFormat.JSON:
        parse_json_object(result.stdout)
    else:
        assert_ndjson_record_envelopes(parse_ndjson_records(result.stdout))


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(
            [
                CliCmd.VERSION,
                CliOpt.OUTPUT_FORMAT,
                OutputFormat.NDJSON.value,
            ],
            id="version",
        ),
        pytest.param(
            [
                CliCmd.CONFIG,
                CliCmd.CONFIG_DEFAULTS,
                CliOpt.OUTPUT_FORMAT,
                OutputFormat.NDJSON.value,
            ],
            id="config-defaults",
        ),
        pytest.param(
            [
                CliCmd.REGISTRY,
                CliCmd.REGISTRY_FILETYPES,
                CliOpt.OUTPUT_FORMAT,
                OutputFormat.NDJSON.value,
            ],
            id="registry-filetypes",
        ),
    ],
)
def test_ndjson_outputs_keep_kind_meta_and_payload_container_contract(args: list[str]) -> None:
    """Representative NDJSON commands should keep the baseline record envelope."""
    result: Result = run_cli(args)
    assert_SUCCESS(result)
    assert_machine_stdout_is_clean(result.stdout)

    assert_ndjson_record_envelopes(
        parse_ndjson_records(result.output),
        expected_detail_level=DetailLevel.BRIEF.value,
    )


def test_processing_ndjson_summary_keeps_kind_meta_and_payload_container_contract(
    tmp_path: Path,
) -> None:
    """Processing NDJSON summary output should keep the baseline record envelope."""
    source: Path = tmp_path / "example.py"
    source.write_text('print("hello")\n', encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.RESULTS_SUMMARY_MODE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
            source.name,
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)
    assert_machine_stdout_is_clean(result.stdout)

    assert_ndjson_record_envelopes(
        parse_ndjson_records(result.output),
        expected_detail_level=DetailLevel.BRIEF.value,
    )
