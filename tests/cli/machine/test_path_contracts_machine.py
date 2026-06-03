# topmark:header:start
#
#   project      : TopMark
#   file         : test_path_contracts_machine.py
#   file_relpath : tests/cli/machine/test_path_contracts_machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Cross-command machine path serialization contract tests.

These tests complement the command-specific machine-output tests by checking
the shared filesystem contract across representative CLI surfaces. Machine
output must serialize path-like fields with stable POSIX separators, regardless
of host platform or nested filesystem layout.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_SUCCESS_or_WOULD_CHANGE
from tests.cli.conftest import run_cli_in
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import parse_ndjson_records
from tests.helpers.ndjson import record_payload
from tests.helpers.paths import assert_machine_path
from tests.helpers.paths import assert_machine_path_fields_are_posix
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.formats import OutputFormat
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def _write_python_file(path: Path) -> None:
    """Write a tiny Python file at `path` for processing and probe tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("print('hello')\n", encoding="utf-8")


def _write_minimal_config(path: Path) -> None:
    """Write a minimal valid TopMark config file for config-dump tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """\
            [fields]
            project = "Demo"

            [header]
            fields = ["project"]
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _processing_json_paths(payload: dict[str, object]) -> list[str]:
    """Return validated per-result paths from a processing JSON payload."""
    results_obj: object | None = payload.get("results")
    assert is_any_list(results_obj)

    paths: list[str] = []
    for result_obj in results_obj:
        assert is_mapping(result_obj)
        result: dict[str, object] = as_object_dict(result_obj)
        paths.append(assert_machine_path(result.get("path")))
    return paths


def _processing_ndjson_paths(records: list[dict[str, object]]) -> list[str]:
    """Return validated per-result paths from processing NDJSON records."""
    paths: list[str] = []
    for record in records:
        if record.get("kind") != "result":
            continue
        payload: dict[str, object] = record_payload(record)
        paths.append(assert_machine_path(payload.get("path")))
    return paths


def _probe_json_paths(payload: dict[str, object]) -> list[str]:
    """Return validated probe paths from a probe JSON payload."""
    probes_obj: object | None = payload.get("probes")
    assert is_any_list(probes_obj)

    paths: list[str] = []
    for probe_obj in probes_obj:
        assert is_mapping(probe_obj)
        probe: dict[str, object] = as_object_dict(probe_obj)
        paths.append(assert_machine_path(probe.get("path")))
    return paths


def _probe_ndjson_paths(records: list[dict[str, object]]) -> list[str]:
    """Return validated probe paths from probe NDJSON records."""
    paths: list[str] = []
    for record in records:
        if record.get("kind") != "probe":
            continue
        payload: dict[str, object] = record_payload(record)
        paths.append(assert_machine_path(payload.get("path")))
    return paths


@pytest.mark.parametrize("command", [CliCmd.CHECK, CliCmd.STRIP])
@pytest.mark.parametrize("output_format", [OutputFormat.JSON, OutputFormat.NDJSON])
def test_processing_machine_output_serializes_nested_result_paths_as_posix(
    tmp_path: Path,
    command: str,
    output_format: OutputFormat,
) -> None:
    """Processing JSON/NDJSON result paths should use POSIX nested paths."""
    relative_path = "src/pkg/example.py"
    _write_python_file(tmp_path / relative_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            output_format.value,
            relative_path,
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    if output_format is OutputFormat.JSON:
        payload: dict[str, object] = parse_json_object(result.output)
        assert_machine_path_fields_are_posix(payload)
        paths: list[str] = _processing_json_paths(payload)
    else:
        records: list[dict[str, object]] = parse_ndjson_records(result.output)
        assert_machine_path_fields_are_posix(records)
        paths = _processing_ndjson_paths(records)

    assert paths == [relative_path]


@pytest.mark.parametrize("output_format", [OutputFormat.JSON, OutputFormat.NDJSON])
def test_probe_machine_output_serializes_nested_probe_paths_as_posix(
    tmp_path: Path,
    output_format: OutputFormat,
) -> None:
    """Probe JSON/NDJSON paths should preserve nested POSIX spellings."""
    relative_path = "src/pkg/example.py"
    _write_python_file(tmp_path / relative_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.PROBE,
            relative_path,
            CliOpt.OUTPUT_FORMAT,
            output_format.value,
        ],
    )
    assert_SUCCESS(result)

    if output_format is OutputFormat.JSON:
        payload: dict[str, object] = parse_json_object(result.output)
        assert_machine_path_fields_are_posix(payload)
        paths: list[str] = _probe_json_paths(payload)
    else:
        records: list[dict[str, object]] = parse_ndjson_records(result.output)
        assert_machine_path_fields_are_posix(records)
        paths = _probe_ndjson_paths(records)

    assert paths == [relative_path]


@pytest.mark.parametrize("output_format", [OutputFormat.JSON, OutputFormat.NDJSON])
def test_config_dump_machine_output_serializes_nested_config_paths_as_posix(
    tmp_path: Path,
    output_format: OutputFormat,
) -> None:
    """Config dump JSON/NDJSON should serialize config provenance paths POSIX-style."""
    relative_config = "config/workspace/topmark.toml"
    _write_minimal_config(tmp_path / relative_config)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.CONFIG_FILES,
            relative_config,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.OUTPUT_FORMAT,
            output_format.value,
        ],
    )
    assert_SUCCESS(result)

    if output_format is OutputFormat.JSON:
        payload: dict[str, object] = parse_json_object(result.output)
        paths: list[str] = assert_machine_path_fields_are_posix(payload)
    else:
        records: list[dict[str, object]] = parse_ndjson_records(result.output)
        paths = assert_machine_path_fields_are_posix(records)

    assert any(path.endswith(relative_config) for path in paths)
