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
from tests.helpers.ndjson import assert_ndjson_meta
from tests.helpers.ndjson import parse_ndjson_records
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.formats import OutputFormat
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

    payload: dict[str, object] = parse_json_object(result.output)
    meta_obj: object | None = payload.get(MachineKey.META.value)
    assert is_mapping(meta_obj)

    meta: dict[str, object] = as_object_dict(meta_obj)
    assert isinstance(meta.get("tool"), str)
    assert isinstance(meta.get("version"), str)
    assert isinstance(meta.get("platform"), str)


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

    payload: dict[str, object] = parse_json_object(result.output)
    meta_obj: object | None = payload.get(MachineKey.META.value)
    assert is_mapping(meta_obj)

    meta: dict[str, object] = as_object_dict(meta_obj)
    assert isinstance(meta.get("tool"), str)
    assert isinstance(meta.get("version"), str)
    assert isinstance(meta.get("platform"), str)


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

    _assert_ndjson_record_envelopes(parse_ndjson_records(result.output))


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

    _assert_ndjson_record_envelopes(parse_ndjson_records(result.output))


def _assert_ndjson_record_envelopes(records: list[dict[str, object]]) -> None:
    """Assert the documented NDJSON `kind` + `meta` + payload-container shape."""
    assert records
    for record in records:
        kind_obj: object | None = record.get(MachineKey.KIND.value)
        assert isinstance(kind_obj, str)
        assert_ndjson_meta(
            record.get(MachineKey.META.value),
            expected_detail_level="brief",
        )
        assert kind_obj in record
