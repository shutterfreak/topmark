# topmark:header:start
#
#   project      : TopMark
#   file         : test_probe_machine.py
#   file_relpath : tests/cli/machine/test_probe_machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""CLI machine-output tests for `topmark probe`.

These tests validate JSON and NDJSON output contracts for the probe command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner
from click.testing import Result

from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import parse_ndjson_records
from tests.helpers.ndjson import record_kinds
from tests.helpers.ndjson import record_payload
from topmark.cli.keys import CliCmd
from topmark.cli.main import cli
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping

if TYPE_CHECKING:
    from pathlib import Path


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
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 0

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
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 0

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
            "--output-format",
            "ndjson",
        ],
    )

    assert result.exit_code == 0

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


def test_probe_ndjson_multiple_files(tmp_path: Path) -> None:
    """NDJSON should emit one probe record per file."""
    file1: Path = tmp_path / "a.py"
    file1.write_text("print('a')\n", encoding="utf-8")

    file2: Path = tmp_path / "b.py"
    file2.write_text("print('b')\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(file1),
            str(file2),
            "--output-format",
            "ndjson",
        ],
    )

    assert result.exit_code == 0

    records: list[dict[str, object]] = parse_ndjson_records(result.output)

    probe_records: list[dict[str, object]] = [r for r in records if r["kind"] == "probe"]
    assert len(probe_records) == 2
