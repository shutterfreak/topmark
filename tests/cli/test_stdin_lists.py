# topmark:header:start
#
#   project      : TopMark
#   file         : test_stdin_lists.py
#   file_relpath : tests/cli/test_stdin_lists.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""List/pattern-list STDIN CLI behavior tests.

This module covers valid STDIN list modes:
- `--files-from -` for newline-delimited file paths,
- `--include-from -` for include patterns,
- `--exclude-from -` for exclude patterns.

Invalid STDIN mode combinations are covered in `tests/cli/test_stdin_errors.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_WOULD_CHANGE
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

# --- helpers ---


def _write_python_file(path: Path) -> None:
    """Write a tiny Python source file at `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("print('hello')\n", encoding="utf-8")


def _json_result_paths(payload: dict[str, object]) -> list[str]:
    """Return validated result paths from a processing JSON payload."""
    results_obj: object | None = payload.get("results")
    assert is_any_list(results_obj)

    paths: list[str] = []
    for result_obj in results_obj:
        assert is_mapping(result_obj)
        result: dict[str, object] = as_object_dict(result_obj)
        paths.append(assert_machine_path(result.get("path")))
    return paths


def _ndjson_result_paths(records: list[dict[str, object]]) -> list[str]:
    """Return validated result paths from processing NDJSON records."""
    paths: list[str] = []
    for record in records:
        if record.get("kind") != "result":
            continue
        payload: dict[str, object] = record_payload(record)
        paths.append(assert_machine_path(payload.get("path")))
    return paths


def _json_probe_paths(payload: dict[str, object]) -> list[str]:
    """Return validated probe paths from a probe JSON payload."""
    probes_obj: object | None = payload.get("probes")
    assert is_any_list(probes_obj)

    paths: list[str] = []
    for probe_obj in probes_obj:
        assert is_mapping(probe_obj)
        probe: dict[str, object] = as_object_dict(probe_obj)
        paths.append(assert_machine_path(probe.get("path")))
    return paths


def _ndjson_probe_paths(records: list[dict[str, object]]) -> list[str]:
    """Return validated probe paths from probe NDJSON records."""
    paths: list[str] = []
    for record in records:
        if record.get("kind") != "probe":
            continue
        payload: dict[str, object] = record_payload(record)
        paths.append(assert_machine_path(payload.get("path")))
    return paths


# --- File-list STDIN mode ---


@pytest.mark.parametrize(
    "command,expected_exit",
    [
        (CliCmd.CHECK, "WOULD_CHANGE"),
        (CliCmd.STRIP, "SUCCESS"),
    ],
)
def test_files_from_stdin_reads_newline_delimited_paths(
    tmp_path: Path,
    command: str,
    expected_exit: str,
) -> None:
    """`--files-from -` should read newline-delimited paths from STDIN."""
    f: Path = tmp_path / "t.py"
    f.write_text("print('y')\n", "utf-8")
    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.FILES_FROM,
            "-",
        ],
        input_text=f.name + "\n",
    )
    if expected_exit == "WOULD_CHANGE":
        assert_WOULD_CHANGE(result)
    else:
        assert_SUCCESS(result)


# --- Machine output path serialization tests ---


@pytest.mark.parametrize("command", [CliCmd.CHECK, CliCmd.STRIP])
@pytest.mark.parametrize("output_format", [OutputFormat.JSON, OutputFormat.NDJSON])
def test_files_from_stdin_machine_output_serializes_nested_paths_as_posix(
    tmp_path: Path,
    command: str,
    output_format: OutputFormat,
) -> None:
    """Machine output for `--files-from -` should keep nested paths POSIX-style."""
    relative_path = "src/pkg/listed.py"
    _write_python_file(tmp_path / relative_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.FILES_FROM,
            "-",
            CliOpt.OUTPUT_FORMAT,
            output_format.value,
        ],
        input_text=f"{relative_path}\n",
    )
    if command == CliCmd.CHECK:
        assert_WOULD_CHANGE(result)
    else:
        assert_SUCCESS(result)

    if output_format is OutputFormat.JSON:
        payload: dict[str, object] = parse_json_object(result.output)
        assert_machine_path_fields_are_posix(payload)
        paths: list[str] = _json_result_paths(payload)
    else:
        records: list[dict[str, object]] = parse_ndjson_records(result.output)
        assert_machine_path_fields_are_posix(records)
        paths = _ndjson_result_paths(records)

    assert paths == [relative_path]


@pytest.mark.parametrize("output_format", [OutputFormat.JSON, OutputFormat.NDJSON])
def test_probe_files_from_stdin_machine_output_serializes_nested_paths_as_posix(
    tmp_path: Path,
    output_format: OutputFormat,
) -> None:
    """Probe machine output should serialize paths loaded from STDIN as POSIX."""
    relative_path = "src/pkg/listed.py"
    _write_python_file(tmp_path / relative_path)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.PROBE,
            CliOpt.FILES_FROM,
            "-",
            CliOpt.OUTPUT_FORMAT,
            output_format.value,
        ],
        input_text=f"{relative_path}\n",
    )
    assert_SUCCESS(result)

    if output_format is OutputFormat.JSON:
        payload: dict[str, object] = parse_json_object(result.output)
        assert_machine_path_fields_are_posix(payload)
        paths: list[str] = _json_probe_paths(payload)
    else:
        records: list[dict[str, object]] = parse_ndjson_records(result.output)
        assert_machine_path_fields_are_posix(records)
        paths = _ndjson_probe_paths(records)

    assert paths == [relative_path]


# --- Pattern-list STDIN mode: include filters ---
def test_include_from_stdin_narrows_candidate_paths(tmp_path: Path) -> None:
    """`--include-from -` should narrow candidates using patterns from STDIN."""
    a: Path = tmp_path / "a.py"
    a.write_text("print()\n", "utf-8")
    b: Path = tmp_path / "b.txt"
    b.write_text("x\n", "utf-8")
    # Provide a superset as paths; include-from narrows the candidates to *.py.
    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.INCLUDE_FROM,
            "-",
            "a.py",
            "b.txt",
        ],
        input_text="*.py\n",
    )
    # Only a.py is considered, and it needs a header.
    assert_WOULD_CHANGE(result)


# --- Pattern-list STDIN mode: exclude filters ---
def test_exclude_from_stdin_removes_candidate_paths(tmp_path: Path) -> None:
    """`--exclude-from -` should remove candidates using patterns from STDIN."""
    a: Path = tmp_path / "a.py"
    a.write_text("print()\n", "utf-8")
    b: Path = tmp_path / "b.py"
    b.write_text("print()\n", "utf-8")
    # Exclude b.py from the candidate set; only a.py remains and needs a header.
    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.EXCLUDE_FROM,
            "-",
            "a.py",
            "b.py",
        ],
        input_text="b.py\n",
    )
    assert_WOULD_CHANGE(result)


# --- Empty STDIN list/pattern input ---
@pytest.mark.parametrize("opt", [CliOpt.FILES_FROM, CliOpt.INCLUDE_FROM, CliOpt.EXCLUDE_FROM])
def test_empty_stdin_for_from_options_keeps_explicit_path_candidates(
    tmp_path: Path, opt: str
) -> None:
    """Empty `*-from -` input should not remove explicit path candidates."""
    # Empty STDIN contributes no additional paths or patterns.
    # The explicit path remains selected, so the command should still run.
    f: Path = tmp_path / "x.py"
    f.write_text("print()\n", "utf-8")
    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            opt,
            "-",
            f.name,
        ],
        input_text="",
    )
    # x.py remains selected and needs a header.
    assert_WOULD_CHANGE(result)
