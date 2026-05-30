# topmark:header:start
#
#   project      : TopMark
#   file         : test_probe_machine.py
#   file_relpath : tests/cli/machine/test_probe_machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""CLI machine-readable output tests for `topmark probe`.

These tests validate JSON and NDJSON output contracts for the probe command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from tests.cli.conftest import assert_CONFIG_ERROR
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_UNSUPPORTED_FILE_TYPE
from tests.helpers.config_diagnostics import assert_config_diagnostics_warning_payload
from tests.helpers.config_diagnostics import assert_overlap_warning_text
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import parse_ndjson_records
from tests.helpers.ndjson import record_kinds
from tests.helpers.ndjson import record_payload
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.main import cli
from topmark.core.formats import OutputFormat
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result
    from pytest import MonkeyPatch


def test_probe_json_output_shape(tmp_path: Path) -> None:
    """JSON output should contain the expected probe structure."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
    )

    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    assert "meta" in payload
    assert "config" in payload
    assert "config_diagnostics" in payload
    assert "probes" in payload

    probes_obj: object = payload["probes"]
    assert is_any_list(probes_obj)
    probes: list[object] = probes_obj
    assert len(probes) == 1

    probe_obj: object = probes[0]
    assert is_mapping(probe_obj)
    probe: dict[str, object] = as_object_dict(probe_obj)
    assert "path" in probe
    assert "status" in probe
    assert "reason" in probe
    assert "selected_file_type" in probe
    assert "selected_processor" in probe
    assert "candidates" in probe


def test_probe_json_candidate_structure(tmp_path: Path) -> None:
    """JSON candidates should expose full probe candidate contract."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
    )

    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)
    probes_obj: object = payload["probes"]
    assert is_any_list(probes_obj)
    probes: list[object] = probes_obj
    assert probes

    probe_obj: object = probes[0]
    assert is_mapping(probe_obj)
    probe: dict[str, object] = as_object_dict(probe_obj)

    candidates_obj: object = probe["candidates"]
    assert is_any_list(candidates_obj)
    candidates: list[object] = candidates_obj
    assert len(candidates) >= 1

    candidate_obj: object = candidates[0]
    assert is_mapping(candidate_obj)
    candidate: dict[str, object] = as_object_dict(candidate_obj)

    assert "qualified_key" in candidate
    assert "namespace" in candidate
    assert "local_key" in candidate
    assert "score" in candidate
    assert "selected" in candidate
    assert "tie_break_rank" in candidate
    assert "match" in candidate

    match_obj: object = candidate["match"]
    assert is_mapping(match_obj)
    match: dict[str, object] = as_object_dict(match_obj)
    assert "extension" in match
    assert "filename" in match
    assert "pattern" in match
    assert "content_probe_allowed" in match
    assert "content_match" in match
    assert "content_error" in match


def test_probe_json_reports_explicit_filtered_input(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """JSON output should expose explicit inputs filtered before probing."""
    monkeypatch.chdir(tmp_path)
    filtered_dir: Path = tmp_path / "__pycache__"
    filtered_dir.mkdir()
    file: Path = filtered_dir / "example.cpython-312.pyc"
    file.write_bytes(b"\x00\x00\x00\x00")
    input_path: str = "__pycache__/example.cpython-312.pyc"

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.EXCLUDE_PATTERNS,
            "__pycache__/",
            input_path,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
    )

    assert_UNSUPPORTED_FILE_TYPE(result)

    payload: dict[str, object] = parse_json_object(result.output)
    probes_obj: object = payload["probes"]
    assert is_any_list(probes_obj)
    probes: list[object] = probes_obj
    assert len(probes) == 1

    probe_obj: object = probes[0]
    assert is_mapping(probe_obj)
    probe: dict[str, object] = as_object_dict(probe_obj)

    assert probe["path"] == input_path

    assert probe["status"] == "filtered"
    assert probe["reason"] == "excluded_by_path_filter"
    assert probe["selected_file_type"] is None
    assert probe["selected_processor"] is None

    candidates_obj: object = probe["candidates"]
    assert is_any_list(candidates_obj)
    assert candidates_obj == []

    assert "match" not in probe


def test_probe_json_omits_directory_filtered_result_when_children_selected(
    tmp_path: Path,
) -> None:
    """JSON output should omit expanded directory synthetic filtered results."""
    directory: Path = tmp_path / "project"
    directory.mkdir()

    python_file: Path = directory / "example.py"
    python_file.write_text("print('hello')\n", encoding="utf-8")

    markdown_file: Path = directory / "README.md"
    markdown_file.write_text("# Example\n", encoding="utf-8")

    html_file: Path = directory / "index.html"
    html_file.write_text("<h1>Example</h1>\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.INCLUDE_FILE_TYPES,
            "python",
            CliOpt.INCLUDE_FILE_TYPES,
            "markdown,toml",
            CliOpt.EXCLUDE_FILE_TYPES,
            "html",
            str(directory),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
    )

    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)
    probes_obj: object = payload["probes"]
    assert is_any_list(probes_obj)
    probes: list[object] = probes_obj
    assert len(probes) == 2

    probe_payloads: list[dict[str, object]] = []
    for probe_obj in probes:
        assert is_mapping(probe_obj)
        probe_payloads.append(as_object_dict(probe_obj))

    paths: set[object] = {probe["path"] for probe in probe_payloads}
    assert str(python_file) in paths
    assert str(markdown_file) in paths
    assert str(directory) not in paths

    statuses: set[object] = {probe["status"] for probe in probe_payloads}
    assert statuses == {"resolved"}


# Regression test: strict config warnings yield machine-readable diagnostics in JSON mode
@pytest.mark.parametrize(
    ("include_file_types", "exclude_file_types", "expected_removed_file_types"),
    [
        ("python", "python", ("topmark:python",)),
        ("python", "topmark:python", ("topmark:python",)),
        ("topmark:python", "python", ("topmark:python",)),
        ("topmark:python", "topmark:python", ("topmark:python",)),
        (
            "topmark:python,topmark:markdown",
            "python,markdown",
            ("topmark:python", "topmark:markdown"),
        ),
    ],
)
def test_probe_json_strict_config_warning_emits_machine_diagnostics(
    tmp_path: Path,
    include_file_types: str,
    exclude_file_types: str,
    expected_removed_file_types: tuple[str, ...],
) -> None:
    """Strict config warnings should remain machine-readable in JSON mode.

    When strict mode escalates a config warning to `CONFIG_ERROR`, probing stops
    before file resolution. JSON output should still be a valid
    config-diagnostics envelope instead of human-oriented error text.
    """
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            CliOpt.STRICT,
            CliOpt.INCLUDE_FILE_TYPES,
            include_file_types,
            CliOpt.EXCLUDE_FILE_TYPES,
            exclude_file_types,
            str(file),
        ],
    )

    assert_CONFIG_ERROR(result)
    payload: dict[str, object] = parse_json_object(result.output)
    assert_config_diagnostics_warning_payload(
        payload,
        expected_removed_file_types,
    )


def test_probe_ndjson_output_shape(tmp_path: Path) -> None:
    """NDJSON output should contain probe records with correct structure."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
        ],
    )

    assert_SUCCESS(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    kinds: list[str] = record_kinds(records)

    assert "probe" in kinds

    probe_record: dict[str, object] = next(r for r in records if r["kind"] == "probe")
    payload: dict[str, object] = record_payload(probe_record)

    assert "path" in payload
    assert "status" in payload
    assert "reason" in payload
    assert "candidates" in payload

    # Ensure no double wrapping (regression test)
    assert "probe" not in payload


def test_probe_ndjson_reports_explicit_filtered_input(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """NDJSON output should expose explicit inputs filtered before probing."""
    monkeypatch.chdir(tmp_path)
    filtered_dir: Path = tmp_path / "__pycache__"
    filtered_dir.mkdir()
    file: Path = filtered_dir / "example.cpython-312.pyc"
    file.write_bytes(b"\x00\x00\x00\x00")
    input_path: str = "__pycache__/example.cpython-312.pyc"

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.EXCLUDE_PATTERNS,
            "__pycache__/",
            input_path,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
        ],
    )

    assert_UNSUPPORTED_FILE_TYPE(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    probe_records: list[dict[str, object]] = [r for r in records if r["kind"] == "probe"]
    assert len(probe_records) == 1

    payload: dict[str, object] = record_payload(probe_records[0])
    assert payload["path"] == input_path

    assert payload["status"] == "filtered"
    assert payload["reason"] == "excluded_by_path_filter"
    assert payload["selected_file_type"] is None
    assert payload["selected_processor"] is None

    candidates_obj: object = payload["candidates"]
    assert is_any_list(candidates_obj)
    assert candidates_obj == []

    assert "match" not in payload


def test_probe_ndjson_reports_missing_input_only_once(tmp_path: Path) -> None:
    """NDJSON output should not duplicate missing inputs as filtered."""
    missing: Path = tmp_path / "topmark-does-not-exist"

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(missing),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
        ],
    )

    assert result.exit_code != 0

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    probe_records: list[dict[str, object]] = [r for r in records if r["kind"] == "probe"]
    assert len(probe_records) == 1

    payload: dict[str, object] = record_payload(probe_records[0])
    assert payload["path"] == str(missing)
    assert payload["status"] == "probe_missing"
    assert payload["reason"] == "no_resolution_probe_result"


def test_probe_ndjson_multiple_files(tmp_path: Path) -> None:
    """NDJSON should emit one probe record per file."""
    file1: Path = tmp_path / "a.py"
    file1.write_text("print('a')\n", encoding="utf-8")

    file2: Path = tmp_path / "b.py"
    file2.write_text("print('b')\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file1),
            str(file2),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
        ],
    )

    assert_SUCCESS(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)

    probe_records: list[dict[str, object]] = [r for r in records if r["kind"] == "probe"]
    assert len(probe_records) == 2


# Regression test: strict config warnings yield machine-readable diagnostics in NDJSON mode
@pytest.mark.parametrize(
    ("include_file_types", "exclude_file_types", "expected_removed_file_types"),
    [
        ("python", "python", ("topmark:python",)),
        ("python", "topmark:python", ("topmark:python",)),
        ("topmark:python", "python", ("topmark:python",)),
        ("topmark:python", "topmark:python", ("topmark:python",)),
        (
            "topmark:python,topmark:markdown",
            "python,markdown",
            ("topmark:python", "topmark:markdown"),
        ),
    ],
)
def test_probe_ndjson_strict_config_warning_emits_machine_diagnostics(
    tmp_path: Path,
    include_file_types: str,
    exclude_file_types: str,
    expected_removed_file_types: tuple[str, ...],
) -> None:
    """Strict config warnings should remain machine-readable in NDJSON mode."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
            CliOpt.STRICT,
            CliOpt.INCLUDE_FILE_TYPES,
            include_file_types,
            CliOpt.EXCLUDE_FILE_TYPES,
            exclude_file_types,
            str(file),
        ],
    )

    assert_CONFIG_ERROR(result)
    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert records

    kinds: list[str] = record_kinds(records)
    assert "config_diagnostics" in kinds
    assert "diagnostic" in kinds

    diagnostic_messages: list[str] = []
    for record in records:
        if record.get("kind") != "diagnostic":
            continue

        diagnostic_obj: object | None = record.get("diagnostic")
        assert is_mapping(diagnostic_obj)
        diagnostic: dict[str, object] = as_object_dict(diagnostic_obj)

        domain_obj: object | None = diagnostic.get("domain")
        level_obj: object | None = diagnostic.get("level")
        message_obj: object | None = diagnostic.get("message")

        assert domain_obj == "config"
        assert level_obj == "warning"
        assert isinstance(message_obj, str)
        diagnostic_messages.append(message_obj)

    assert diagnostic_messages
    assert_overlap_warning_text(
        "\n".join(diagnostic_messages),
        expected_removed_file_types,
    )
