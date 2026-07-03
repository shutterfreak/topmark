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
from tests.cli.conftest import assert_FILE_NOT_FOUND
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_UNSUPPORTED_FILE_TYPE
from tests.helpers.config import make_frozen_config
from tests.helpers.config_diagnostics import assert_config_diagnostics_warning_payload
from tests.helpers.config_diagnostics import assert_overlap_warning_text
from tests.helpers.console import CapturedConsole
from tests.helpers.console import make_captured_console
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import assert_ndjson_meta
from tests.helpers.ndjson import parse_ndjson_records
from tests.helpers.ndjson import record_kinds
from tests.helpers.ndjson import record_payload
from tests.helpers.paths import symlink_or_skip
from tests.helpers.pipeline import make_pipeline_context
from topmark.cli.emitters.machine import emit_probe_results_machine
from topmark.cli.emitters.machine import emit_probe_stream_json_machine
from topmark.cli.emitters.machine import emit_probe_stream_machine
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.main import cli
from topmark.core.formats import OutputFormat
from topmark.core.machine.schemas import MetaPayload
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping
from topmark.pipeline.machine.streaming import MachineProcessingResultEvent
from topmark.pipeline.machine.streaming import MachineRunCompletedEvent
from topmark.pipeline.machine.streaming import MachineRunStartedEvent
from topmark.pipeline.result import ProcessingResult
from topmark.toml.resolution import ResolvedTopmarkTomlSources
from topmark.utils.path import format_machine_path

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result
    from pytest import MonkeyPatch

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext


def _machine_meta() -> MetaPayload:
    """Return stable test metadata payload for machine-emitter tests."""
    return MetaPayload(
        tool="topmark",
        version="test",
        platform="test",
    )


def _empty_resolved_toml_sources() -> ResolvedTopmarkTomlSources:
    """Return an empty TOML resolution result for machine-emitter tests."""
    return ResolvedTopmarkTomlSources(
        sources=[],
        writer_options=None,
        strict=None,
    )


def _probe_result(tmp_path: Path) -> tuple[FrozenConfig, ProcessingResult]:
    """Return a minimal durable probe result for emitter tests."""
    cfg: FrozenConfig = make_frozen_config()
    ctx: ProcessingContext = make_pipeline_context(path=tmp_path / "example.py", cfg=cfg)
    return cfg, ProcessingResult.from_context(ctx)


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


def test_probe_json_output_separates_payload_from_stderr(tmp_path: Path) -> None:
    """Probe JSON output should keep payload on STDOUT.

    Probe JSON output keeps payload on STDOUT, nothing on STDERR.
    """
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
    assert result.stderr == ""
    payload: dict[str, object] = parse_json_object(result.stdout)
    assert "probes" in payload


def test_probe_json_content_stdin_uses_payload_stdout_and_cleans_tempfile() -> None:
    """Probe JSON should support content-on-STDIN without STDERR chatter.

    Regression: JSON probe should support content-on-STDIN and clean up tempfiles.
    """
    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            "-",
            CliOpt.STDIN_FILENAME,
            "example.py",
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
        input="print('hello')\n",
    )

    assert_SUCCESS(result)
    assert result.stderr == ""
    payload: dict[str, object] = parse_json_object(result.stdout)
    probes_obj: object = payload["probes"]
    assert is_any_list(probes_obj)
    probes: list[object] = probes_obj
    assert len(probes) == 1


def test_probe_json_symlink_input_serializes_canonical_target_path(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Probe JSON paths should use the canonical processing target for symlinked inputs."""
    monkeypatch.chdir(tmp_path)
    target: Path = tmp_path / "real" / "source.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('hello')\n", encoding="utf-8")
    link: Path = symlink_or_skip(tmp_path / "links" / "source-link.py", target)

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(link.relative_to(tmp_path)),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
    )

    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)
    probes_obj: object = payload["probes"]
    assert is_any_list(probes_obj)
    probes: list[object] = probes_obj
    assert len(probes) == 1

    probe_obj: object = probes[0]
    assert is_mapping(probe_obj)
    probe: dict[str, object] = as_object_dict(probe_obj)

    assert probe["path"] == "real/source.py"


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
    assert format_machine_path(python_file) in paths
    assert format_machine_path(markdown_file) in paths
    assert format_machine_path(directory) not in paths

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


# NDJSON probe records should expose the standard brief metadata contract.
def test_probe_ndjson_output_includes_brief_meta_on_each_record(
    tmp_path: Path,
) -> None:
    """Probe NDJSON records should expose the standard brief metadata contract."""
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
    assert records

    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")


def test_probe_ndjson_symlink_input_serializes_canonical_target_path(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Probe NDJSON paths should use the canonical processing target for symlinked inputs."""
    monkeypatch.chdir(tmp_path)
    target: Path = tmp_path / "real" / "source.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('hello')\n", encoding="utf-8")
    link: Path = symlink_or_skip(tmp_path / "links" / "source-link.py", target)

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            str(link.relative_to(tmp_path)),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
        ],
    )

    assert_SUCCESS(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    probe_records: list[dict[str, object]] = [
        record for record in records if record["kind"] == "probe"
    ]
    assert len(probe_records) == 1

    payload: dict[str, object] = record_payload(probe_records[0])
    assert payload["path"] == "real/source.py"


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
            format_machine_path(missing),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
        ],
    )

    assert_FILE_NOT_FOUND(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    probe_records: list[dict[str, object]] = [r for r in records if r["kind"] == "probe"]
    assert len(probe_records) == 1

    payload: dict[str, object] = record_payload(probe_records[0])
    assert payload["path"] == format_machine_path(missing)
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


# Quiet TEXT probe should consume the stream before computing semantic exit status.
def test_probe_text_quiet_consumes_stream_before_unresolved_exit(
    tmp_path: Path,
) -> None:
    """Quiet TEXT probe should consume the stream before computing semantic exit status."""
    file: Path = tmp_path / "example.unknown"
    file.write_text("plain text\n", encoding="utf-8")

    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.QUIET,
            str(file),
        ],
    )

    assert_UNSUPPORTED_FILE_TYPE(result)
    assert result.output == ""


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


def test_probe_ndjson_output_separates_payload_from_stderr(tmp_path: Path) -> None:
    """Probe NDJSON output should keep payload records on STDOUT.

    Probe NDJSON output keeps payload records on STDOUT, nothing on STDERR.
    """
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
    assert result.stderr == ""
    records: list[dict[str, object]] = parse_ndjson_records(result.stdout)
    assert "probe" in record_kinds(records)


def test_probe_ndjson_content_stdin_uses_payload_stdout_and_cleans_tempfile() -> None:
    """Probe NDJSON should support content-on-STDIN without STDERR chatter.

    Regression: NDJSON probe should support content-on-STDIN and clean up tempfiles.
    """
    runner = CliRunner()
    result: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            "-",
            CliOpt.STDIN_FILENAME,
            "example.py",
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
        ],
        input="print('hello')\n",
    )

    assert_SUCCESS(result)
    assert result.stderr == ""
    records: list[dict[str, object]] = parse_ndjson_records(result.stdout)
    assert "probe" in record_kinds(records)


# --- Emitter helper tests ---


@pytest.mark.parametrize("fmt", [OutputFormat.JSON, OutputFormat.NDJSON])
def test_emit_probe_results_machine_emits_legacy_probe_payload(
    tmp_path: Path,
    fmt: OutputFormat,
) -> None:
    """Legacy probe emitter should still write machine payloads."""
    cfg, result = _probe_result(tmp_path)
    captured: CapturedConsole = make_captured_console()

    emit_probe_results_machine(
        console=captured.console,
        meta=_machine_meta(),
        config=cfg,
        resolved_toml=_empty_resolved_toml_sources(),
        results=(result,),
        fmt=fmt,
    )

    assert captured.out.getvalue().strip() != ""
    assert captured.err.getvalue() == ""
    if fmt is OutputFormat.JSON:
        assert not captured.out.getvalue().endswith("\n")
    else:
        assert captured.out.getvalue().endswith("\n")


def test_emit_probe_results_machine_rejects_non_machine_format(tmp_path: Path) -> None:
    """Legacy probe emitter should reject non-machine formats."""
    cfg, result = _probe_result(tmp_path)
    captured: CapturedConsole = make_captured_console()

    with pytest.raises(ValueError, match="Unsupported machine-readable output format"):
        emit_probe_results_machine(
            console=captured.console,
            meta=_machine_meta(),
            config=cfg,
            resolved_toml=_empty_resolved_toml_sources(),
            results=(result,),
            fmt=OutputFormat.TEXT,
        )

    assert captured.out.getvalue() == ""
    assert captured.err.getvalue() == ""


def test_emit_probe_stream_json_machine_emits_stream_json_payload(
    tmp_path: Path,
) -> None:
    """Probe stream JSON emitter should write one newline-free JSON payload."""
    cfg, result = _probe_result(tmp_path)
    captured: CapturedConsole = make_captured_console()

    emit_probe_stream_json_machine(
        console=captured.console,
        meta=_machine_meta(),
        config=cfg,
        resolved_toml=_empty_resolved_toml_sources(),
        events=(
            MachineRunStartedEvent(
                command="probe",
                selected_count=1,
                paths=(result.path,),
            ),
            MachineProcessingResultEvent(
                command="probe",
                index=0,
                result=result,
            ),
            MachineRunCompletedEvent(command="probe"),
        ),
    )

    assert captured.err.getvalue() == ""
    assert "probes" in captured.out.getvalue()
    assert not captured.out.getvalue().endswith("\n")


def test_emit_probe_stream_machine_emits_stream_ndjson_payload(
    tmp_path: Path,
) -> None:
    """Probe stream NDJSON emitter should write line-delimited records."""
    cfg, result = _probe_result(tmp_path)
    captured: CapturedConsole = make_captured_console()

    emit_probe_stream_machine(
        console=captured.console,
        meta=_machine_meta(),
        config=cfg,
        resolved_toml=_empty_resolved_toml_sources(),
        events=(
            MachineRunStartedEvent(
                command="probe",
                selected_count=1,
                paths=(result.path,),
            ),
            MachineProcessingResultEvent(
                command="probe",
                index=0,
                result=result,
            ),
            MachineRunCompletedEvent(command="probe"),
        ),
    )

    assert captured.err.getvalue() == ""
    assert "probe" in captured.out.getvalue()
    assert captured.out.getvalue().endswith("\n")
