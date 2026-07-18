# topmark:header:start
#
#   project      : TopMark
#   file         : test_processing_machine.py
#   file_relpath : tests/cli/machine/test_processing_machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output contract tests for TopMark processing CLI commands.

This module verifies the JSON and NDJSON output emitted by processing commands
such as `topmark check` and `topmark strip` when machine-readable output modes
are enabled (`--output-format json` and `--output-format ndjson`).

The tests serve as high-level contract checks to ensure that:

- processing commands emit a well-formed machine payload containing at least:
    - a `meta` block with `tool` and `version`,
    - a flattened `config` payload,
    - a `config_diagnostics` payload,
    - and either detailed per-file `results` or aggregated `summary` rows,
      depending on the selected output mode;
- NDJSON summary mode emits the expected record kinds for processing commands;
- the output follows the documented machine schema
  (see `docs/usage/machine-output.md`).

These tests intentionally avoid checking full schema content
(e.g. every per-axis status field), focusing instead on structural stability,
required top-level keys, and representative nested shapes.

All CLI invocations are executed via Click's `CliRunner`, using the helpers in
`tests.cli.conftest` to control the working directory and assert exit codes.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from typing import cast

import pytest

from tests.cli.conftest import assert_CONFIG_ERROR
from tests.cli.conftest import assert_SUCCESS_or_WOULD_CHANGE
from tests.cli.conftest import run_cli_in
from tests.helpers.config import make_frozen_config
from tests.helpers.config_diagnostics import assert_config_diagnostics_warning_payload
from tests.helpers.config_diagnostics import assert_overlap_warning_text
from tests.helpers.console import CapturedConsole
from tests.helpers.console import make_captured_console
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import assert_ndjson_meta
from tests.helpers.ndjson import parse_ndjson_records
from tests.helpers.ndjson import record_kinds
from tests.helpers.paths import symlink_or_skip
from tests.helpers.pipeline import make_pipeline_context
from topmark.cli.emitters.machine import emit_config_check_machine
from topmark.cli.emitters.machine import emit_config_diagnostics_machine
from topmark.cli.emitters.machine import emit_config_machine
from topmark.cli.emitters.machine import emit_machine
from topmark.cli.emitters.machine import emit_processing_stream_json_machine
from topmark.cli.emitters.machine import emit_processing_stream_machine
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.formats import OutputFormat
from topmark.core.machine.schemas import MetaPayload
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping
from topmark.pipeline.machine.envelopes import build_processing_results_stream_json_envelope
from topmark.pipeline.machine.envelopes import iter_processing_results_stream_ndjson_records
from topmark.pipeline.machine.streaming import MachineProcessingResultEvent
from topmark.pipeline.machine.streaming import MachineRunCompletedEvent
from topmark.pipeline.machine.streaming import MachineRunStartedEvent
from topmark.pipeline.machine.streaming import iter_machine_processing_stream
from topmark.pipeline.result import ProcessingResult
from topmark.toml.resolution import ResolvedTopmarkTomlSources

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral


class _WindowsStylePath:
    """Minimal path double for exercising Windows-native string serialization."""

    def __str__(self) -> str:
        """Return the Windows-native spelling produced by `Path.__str__()` on Windows."""
        # Return a string that, when JSON-escaped, will yield "C:/Repo/src/example.py"
        return r"C:\Repo\src\example.py"

    def as_posix(self) -> str:
        """Return the POSIX spelling expected for processing machine output."""
        return "C:/Repo/src/example.py"


def _processing_result(tmp_path: Path) -> tuple[FrozenConfig, ProcessingResult]:
    """Return a minimal durable processing result for emitter tests."""
    cfg: FrozenConfig = make_frozen_config()
    ctx: ProcessingContext = make_pipeline_context(path=tmp_path / "example.py", cfg=cfg)
    return cfg, ProcessingResult.from_context(ctx)


def _machine_meta() -> MetaPayload:
    """Return stable test metadata payload for machine-envelope builders."""
    return MetaPayload(
        tool="topmark",
        version="test",
        platform="test",
    )


def _empty_resolved_toml_sources() -> ResolvedTopmarkTomlSources:
    """Return an empty TOML resolution result for envelope-builder tests."""
    return ResolvedTopmarkTomlSources(
        sources=[],
        writer_options=None,
        strict=None,
    )


def _write_plain_python_file(tmp_path: Path) -> Path:
    """Write a Python file without a TopMark header."""
    path: Path = tmp_path / "example.py"
    path.write_text('print("hello")\n', encoding="utf-8")
    return path


def _write_markdown_file_with_topmark_header(tmp_path: Path) -> Path:
    """Write a Markdown file containing a removable TopMark header."""
    path: Path = tmp_path / "README.md"
    path.write_text(
        "\n".join(
            [
                "<!--",
                "topmark:header:start",
                "",
                "  project   : Example",
                "  file      : README.md",
                "  license   : MIT",
                "",
                "topmark:header:end",
                "-->",
                "",
                "# Example",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_emit_machine_skips_empty_serialized_output() -> None:
    """Machine emitter should not write output for empty serialized payloads."""
    captured: CapturedConsole = make_captured_console()

    emit_machine("", console=captured.console)

    assert captured.out.getvalue() == ""
    assert captured.err.getvalue() == ""


@pytest.mark.parametrize(
    "emitter",
    [
        emit_config_machine,
        emit_config_diagnostics_machine,
        emit_config_check_machine,
    ],
)
@pytest.mark.parametrize(
    "fmt",
    [
        OutputFormat.TEXT,
        OutputFormat.MARKDOWN,
    ],
)
def test_config_machine_emitters_reject_human_output_formats(
    emitter: object,
    fmt: OutputFormat,
) -> None:
    """Config machine emitters should propagate serializer format rejection."""
    cfg: FrozenConfig = make_frozen_config()
    captured: CapturedConsole = make_captured_console()

    with pytest.raises(ValueError) as exc_info:
        if emitter is emit_config_machine:
            emit_config_machine(
                console=captured.console,
                meta=_machine_meta(),
                config=cfg,
                resolved_toml=_empty_resolved_toml_sources(),
                fmt=fmt,
            )
        elif emitter is emit_config_diagnostics_machine:
            emit_config_diagnostics_machine(
                console=captured.console,
                meta=_machine_meta(),
                config=cfg,
                fmt=fmt,
            )
        else:
            emit_config_check_machine(
                console=captured.console,
                meta=_machine_meta(),
                config=cfg,
                resolved_toml=_empty_resolved_toml_sources(),
                strict=True,
                ok=True,
                fmt=fmt,
            )

    assert str(exc_info.value) == f"Unsupported machine-readable output format: {fmt!r}"


# --- Path serialization contract tests ---


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_json_detail_diff_payload_shape(tmp_path: Path, command: str) -> None:
    """JSON detail mode should embed per-file diff payloads under result entries."""
    path: Path = (
        _write_plain_python_file(tmp_path)
        if command == CliCmd.CHECK
        else _write_markdown_file_with_topmark_header(tmp_path)
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.RENDER_DIFF,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            str(path.relative_to(tmp_path)),
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, object] = parse_json_object(result.output)
    results_obj: object = payload["results"]
    assert is_any_list(results_obj)
    results: list[object] = results_obj
    assert len(results) == 1

    first_obj: object = results[0]
    assert is_mapping(first_obj)
    first: dict[str, object] = as_object_dict(first_obj)
    assert "diff" in first

    diff_obj: object | None = first.get("diff")
    assert is_mapping(diff_obj)
    diff: dict[str, object] = as_object_dict(diff_obj)
    assert "path" not in diff

    diff_text_obj: object | None = diff.get("diff_text")
    assert isinstance(diff_text_obj, str)
    assert f"--- {path.name}" in diff_text_obj
    assert f"+++ {path.name}" in diff_text_obj
    assert "@@" in diff_text_obj

    detail_obj: object | None = first.get("detail")
    if detail_obj is not None:
        assert is_mapping(detail_obj)
        detail: dict[str, object] = as_object_dict(detail_obj)
        assert "diff_text" not in detail


@pytest.mark.parametrize(
    ("command", "output_format"),
    [
        pytest.param(CliCmd.CHECK, OutputFormat.JSON, id="check-json"),
        pytest.param(CliCmd.CHECK, OutputFormat.NDJSON, id="check-ndjson"),
        pytest.param(CliCmd.STRIP, OutputFormat.JSON, id="strip-json"),
        pytest.param(CliCmd.STRIP, OutputFormat.NDJSON, id="strip-ndjson"),
    ],
)
def test_processing_machine_detail_output_separates_payload_from_stderr(
    tmp_path: Path,
    command: str,
    output_format: OutputFormat,
) -> None:
    """Processing machine detail output should keep payload on STDOUT.

    Machine detail output keeps payload on STDOUT, nothing on STDERR.
    """
    path: Path = (
        _write_plain_python_file(tmp_path)
        if command == CliCmd.CHECK
        else _write_markdown_file_with_topmark_header(tmp_path)
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            output_format.value,
            str(path.relative_to(tmp_path)),
        ],
    )

    assert_SUCCESS_or_WOULD_CHANGE(result)
    assert result.stderr == ""

    if output_format is OutputFormat.JSON:
        payload: dict[str, object] = parse_json_object(result.stdout)
        assert "results" in payload
        assert "summary" not in payload
        return

    records: list[dict[str, object]] = parse_ndjson_records(result.stdout)
    assert "result" in record_kinds(records)
    assert "summary" not in record_kinds(records)


@pytest.mark.parametrize(
    ("command", "output_format"),
    [
        pytest.param(CliCmd.CHECK, OutputFormat.JSON, id="check-json"),
        pytest.param(CliCmd.CHECK, OutputFormat.NDJSON, id="check-ndjson"),
        pytest.param(CliCmd.STRIP, OutputFormat.JSON, id="strip-json"),
        pytest.param(CliCmd.STRIP, OutputFormat.NDJSON, id="strip-ndjson"),
    ],
)
def test_processing_machine_summary_diff_omits_diff_payload_and_warns(
    tmp_path: Path,
    command: str,
    output_format: OutputFormat,
) -> None:
    """Machine summary mode should warn and omit per-file diff payloads."""
    path: Path = (
        _write_plain_python_file(tmp_path)
        if command == CliCmd.CHECK
        else _write_markdown_file_with_topmark_header(tmp_path)
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.RENDER_DIFF,
            CliOpt.RESULTS_SUMMARY_MODE,
            CliOpt.OUTPUT_FORMAT,
            output_format.value,
            str(path.relative_to(tmp_path)),
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)
    assert (
        f"--diff does not emit per-file diff payloads when --summary is enabled "
        f"with --output-format={output_format.value}."
    ) in result.stderr
    assert "Note:" not in result.stdout

    if output_format is OutputFormat.JSON:
        payload: dict[str, object] = parse_json_object(result.stdout)
        assert "summary" in payload
        assert "results" not in payload
        assert "diff" not in payload
        assert "diffs" not in payload
        return

    records: list[dict[str, object]] = parse_ndjson_records(result.stdout)
    assert "summary" in record_kinds(records)
    assert "result" not in record_kinds(records)
    assert "diff" not in record_kinds(records)


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_ndjson_detail_diff_record_shape(tmp_path: Path, command: str) -> None:
    """NDJSON detail mode should emit adjacent standalone diff records."""
    path: Path = (
        _write_plain_python_file(tmp_path)
        if command == CliCmd.CHECK
        else _write_markdown_file_with_topmark_header(tmp_path)
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.RENDER_DIFF,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
            str(path.relative_to(tmp_path)),
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    kinds: list[str] = record_kinds(records)
    assert "result" in kinds
    assert "diff" in kinds

    result_index: int = kinds.index("result")
    assert kinds[result_index + 1] == "diff"

    result_obj: object | None = records[result_index].get("result")
    assert is_mapping(result_obj)
    result_payload: dict[str, object] = as_object_dict(result_obj)
    assert "detail" not in result_payload
    assert "diff" not in result_payload

    diff_obj: object | None = records[result_index + 1].get("diff")
    assert is_mapping(diff_obj)
    diff_payload: dict[str, object] = as_object_dict(diff_obj)
    assert diff_payload.get("path") == path.name

    diff_text_obj: object | None = diff_payload.get("diff_text")
    assert isinstance(diff_text_obj, str)
    assert f"--- {path.name}" in diff_text_obj
    assert f"+++ {path.name}" in diff_text_obj
    assert "@@" in diff_text_obj


def test_emit_processing_stream_json_machine_emits_stream_json_payload(
    tmp_path: Path,
) -> None:
    """Processing stream JSON emitter should write one newline-free JSON payload."""
    cfg, result = _processing_result(tmp_path)
    captured: CapturedConsole = make_captured_console()

    emit_processing_stream_json_machine(
        console=captured.console,
        meta=_machine_meta(),
        config=cfg,
        resolved_toml=_empty_resolved_toml_sources(),
        events=(
            MachineRunStartedEvent(
                command="check",
                selected_count=1,
                paths=(result.path,),
            ),
            MachineProcessingResultEvent(
                command="check",
                index=0,
                result=result,
            ),
            MachineRunCompletedEvent(command="check"),
        ),
        summary_mode=False,
    )

    assert captured.err.getvalue() == ""
    assert "results" in captured.out.getvalue()
    assert not captured.out.getvalue().endswith("\n")


def test_emit_processing_stream_machine_emits_stream_ndjson_payload(
    tmp_path: Path,
) -> None:
    """Processing stream NDJSON emitter should write line-delimited records."""
    cfg, result = _processing_result(tmp_path)
    captured: CapturedConsole = make_captured_console()

    emit_processing_stream_machine(
        console=captured.console,
        meta=_machine_meta(),
        config=cfg,
        resolved_toml=_empty_resolved_toml_sources(),
        events=(
            MachineRunStartedEvent(
                command="check",
                selected_count=1,
                paths=(result.path,),
            ),
            MachineProcessingResultEvent(
                command="check",
                index=0,
                result=result,
            ),
            MachineRunCompletedEvent(command="check"),
        ),
        summary_mode=False,
    )

    assert captured.err.getvalue() == ""
    assert "result" in captured.out.getvalue()
    assert captured.out.getvalue().endswith("\n")


# ----- JSON -----


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_json_includes_meta(tmp_path: Path, command: str) -> None:
    """Ensure JSON machine-readable output for `check` / `strip` includes meta/tool/version.

    This parametrized test runs `check` and `strip` in JSON mode and verifies
    that the top-level payload contains a `meta` block with `tool` and
    `version`. It acts as a shared smoke test for processing commands that
    emit machine-readable output.
    """
    # Create a tiny fake project so `check` has something to scan
    (tmp_path / "example.py").write_text(
        "#!/usr/bin/env python3\nprint('hi')\n",
        encoding="utf-8",
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            ".",
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, object] = parse_json_object(result.output)
    assert "meta" in payload

    meta_obj: object | None = payload.get("meta")
    assert is_mapping(meta_obj)
    meta: dict[str, object] = as_object_dict(meta_obj)

    tool_obj: object | None = meta.get("tool")
    assert isinstance(tool_obj, str)
    assert tool_obj == "topmark"

    version_obj: object | None = meta.get("version")
    assert isinstance(version_obj, str)
    assert version_obj != ""


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_json_detail_shape(tmp_path: Path, command: str) -> None:
    """Check JSON detail-mode shape for `check` / `strip` with `--output-format json`.

    Verifies that the top-level wrapper and a single per-file result entry
    follow the documented machine-readable output schema (see `docs/usage/machine-output.md`).
    This focuses on structural stability (keys and types) rather than exact
    labels or counts and applies equally to `check` and `strip`. The optional
    `detail` object is intentionally not required because empty detail payloads
    are suppressed.
    """
    (tmp_path / "example.py").write_text(
        "#!/usr/bin/env python3\nprint('hi')\n",
        encoding="utf-8",
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            ".",
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, object] = parse_json_object(result.output)

    # Top-level wrapper keys
    assert "meta" in payload
    assert "config" in payload
    assert "config_diagnostics" in payload
    assert "results" in payload

    results_raw: object = payload["results"]
    assert is_any_list(results_raw)
    results_list: list[object] = results_raw
    assert results_list  # At least one result

    first_raw: object = results_list[0]
    assert is_mapping(first_raw)
    first: dict[str, object] = as_object_dict(first_raw)

    # Basic per-file keys
    for key in (
        "path",
        "file_type",
        "steps",
        "step_axes",
        "status",
        "outcome",
    ):
        assert key in first
    assert "views" not in first
    assert "diff" not in first
    detail_raw: object | None = first.get("detail")
    if detail_raw is not None:
        assert is_mapping(detail_raw)
        detail: dict[str, object] = as_object_dict(detail_raw)
        assert "diff_text" not in detail

    # steps: list of strings
    steps_raw: object = first["steps"]
    assert is_any_list(steps_raw)
    steps: list[object] = steps_raw
    assert steps
    for s in steps:
        assert isinstance(s, str)

    # step_axes: mapping step name -> list of axes
    step_axes_raw: object = first["step_axes"]
    assert is_mapping(step_axes_raw)
    step_axes: dict[str, object] = as_object_dict(step_axes_raw)
    assert step_axes  # some step axes present

    # At least one entry maps to a non-empty list of axis names
    has_non_empty_axis_list = False
    for value in step_axes.values():
        assert isinstance(value, list)
        if value:
            has_non_empty_axis_list = True
    assert has_non_empty_axis_list

    # status: axis -> {axis, name, label}
    status_obj: object = first["status"]
    assert is_mapping(status_obj)
    status: dict[str, object] = as_object_dict(status_obj)
    # We expect at least the "resolve" axis entry
    assert "resolve" in status
    resolve_status_obj: object = status["resolve"]
    assert is_mapping(resolve_status_obj)
    resolve_status: dict[str, object] = as_object_dict(resolve_status_obj)
    assert resolve_status.get("axis") == "resolve"
    assert isinstance(resolve_status.get("name"), str)
    assert isinstance(resolve_status.get("label"), str)

    # outcome: should be a mapping
    outcome_obj: object = first["outcome"]
    assert is_mapping(outcome_obj)


# --- Path serialization contract tests ---


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_json_detail_path_serializes_windows_style_path_as_posix(
    tmp_path: Path,
    command: PipelineKindLiteral,
) -> None:
    """Processing JSON result paths should use POSIX separators in detail mode."""
    cfg: FrozenConfig = make_frozen_config()
    ctx: ProcessingContext = make_pipeline_context(path=tmp_path / "example.py", cfg=cfg)

    # The production attribute is a concrete Path, but this contract test needs
    # to exercise Windows-native `str(path)` behavior on every host platform.
    processing_result: ProcessingResult = replace(
        ProcessingResult.from_context(ctx),
        path=cast("Path", _WindowsStylePath()),
    )

    payload: dict[str, object] = build_processing_results_stream_json_envelope(
        meta=_machine_meta(),
        config=cfg,
        resolved_toml=_empty_resolved_toml_sources(),
        events=iter_machine_processing_stream([processing_result], command=command),
        summary_mode=False,
    )

    results_obj: object = payload["results"]
    assert is_any_list(results_obj)
    results: list[object] = results_obj
    assert len(results) == 1

    first_obj: object = results[0]
    assert is_mapping(first_obj)
    first: dict[str, object] = as_object_dict(first_obj)

    assert first.get("path") == "C:/Repo/src/example.py"


# --- Symlink canonical path serialization tests ---


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_json_detail_symlink_input_serializes_canonical_target_path(
    tmp_path: Path,
    command: str,
) -> None:
    """Processing JSON detail paths should use the canonical processing target."""
    target: Path = tmp_path / "real" / "source.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('hello')\n", encoding="utf-8")
    link: Path = symlink_or_skip(tmp_path / "links" / "source-link.py", target)

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            str(link.relative_to(tmp_path)),
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, object] = parse_json_object(result.output)
    results_obj: object = payload["results"]
    assert is_any_list(results_obj)
    results: list[object] = results_obj
    assert len(results) == 1

    first_obj: object = results[0]
    assert is_mapping(first_obj)
    first: dict[str, object] = as_object_dict(first_obj)

    assert first.get("path") == "real/source.py"


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_json_summary_shape(tmp_path: Path, command: str) -> None:
    """Check JSON summary-mode shape for `check` / `strip` with `--summary`.

    Ensures that the top-level JSON object contains a `summary` map keyed by
    bucket name, where each entry has at least `count` (int) and `label` (str).
    This test is parametrized over `check` and `strip`, which share the same
    summary-mode JSON structure.
    """
    (tmp_path / "example.py").write_text(
        "#!/usr/bin/env python3\nprint('hi')\n",
        encoding="utf-8",
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            CliOpt.RESULTS_SUMMARY_MODE,
            ".",
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, object] = parse_json_object(result.output)

    # Top-level wrapper still includes meta/config/config_diagnostics
    assert "meta" in payload
    assert "config" in payload
    assert "config_diagnostics" in payload
    # Summary replaces the results array in summary-mode
    assert "summary" in payload

    summary_obj: object = payload["summary"]
    assert is_any_list(summary_obj)
    summary_rows: list[object] = summary_obj
    assert summary_rows  # at least one summary row

    first_obj: object = summary_rows[0]
    assert is_mapping(first_obj)
    first: dict[str, object] = as_object_dict(first_obj)
    assert isinstance(first.get("outcome"), str)
    assert isinstance(first.get("reason"), str)
    assert isinstance(first.get("count"), int)


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_json_summary_rows_do_not_use_legacy_key_label_shape(
    tmp_path: Path,
    command: str,
) -> None:
    """Ensure JSON summary rows use outcome/reason/count and not legacy key/label fields."""
    (tmp_path / "example.py").write_text(
        "#!/usr/bin/env python3\nprint('hi')\n",
        encoding="utf-8",
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            CliOpt.RESULTS_SUMMARY_MODE,
            ".",
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, object] = parse_json_object(result.output)

    summary_obj: object = payload["summary"]
    assert is_any_list(summary_obj)
    summary_rows: list[object] = summary_obj
    assert summary_rows

    for row_obj in summary_rows:
        assert is_mapping(row_obj)
        row: dict[str, object] = as_object_dict(row_obj)
        assert "outcome" in row
        assert "reason" in row
        assert "count" in row
        assert "key" not in row
        assert "label" not in row


# Regression test: strict config warnings should remain machine-readable in JSON mode
@pytest.mark.parametrize("command", [CliCmd.CHECK, CliCmd.STRIP])
def test_processing_json_strict_config_warning_emits_machine_diagnostics(
    tmp_path: Path,
    command: str,
) -> None:
    """Strict config warnings should remain machine-readable in JSON mode.

    When strict mode escalates a config warning to `CONFIG_ERROR`, processing
    stops before file resolution. JSON output should still be a valid
    config-diagnostics envelope instead of human-oriented error text.
    """
    (tmp_path / "example.py").write_text("print('hi')\n", encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            CliOpt.STRICT,
            CliOpt.INCLUDE_FILE_TYPES,
            "topmark:python,topmark:markdown",
            CliOpt.EXCLUDE_FILE_TYPES,
            "python,markdown",
            ".",
        ],
    )

    assert_CONFIG_ERROR(result)
    payload: dict[str, object] = parse_json_object(result.output)
    assert_config_diagnostics_warning_payload(
        payload,
        ("topmark:python", "topmark:markdown"),
    )


# ----- NDJSON -----


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_ndjson_kinds_with_summary(tmp_path: Path, command: str) -> None:
    """Ensure NDJSON `--summary` output for `check` / `strip` emits config and summary records.

    We expect, for both `check` and `strip`:
    - one `config` record,
    - one `config_diagnostics` record,
    - one or more `summary` records (per bucket).

    Per-file `result` records are not emitted in NDJSON summary mode.
    """
    (tmp_path / "example.py").write_text(
        "#!/usr/bin/env python3\nprint('hi')\n",
        encoding="utf-8",
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
            CliOpt.RESULTS_SUMMARY_MODE,
            ".",
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert records

    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")

    kinds: list[str] = record_kinds(records)
    for record, kind_obj in zip(records, kinds, strict=False):
        if kind_obj == "summary":
            summary_obj: object | None = record.get("summary")
            assert is_mapping(summary_obj)
            summary: dict[str, object] = as_object_dict(summary_obj)

            outcome_obj: object | None = summary.get("outcome")
            reason_obj: object | None = summary.get("reason")
            count_obj: object | None = summary.get("count")
            assert isinstance(outcome_obj, str)
            assert isinstance(reason_obj, str)
            assert isinstance(count_obj, int)

    kinds_set: set[str] = set(kinds)
    assert "config" in kinds_set
    assert "config_diagnostics" in kinds_set
    assert "summary" in kinds_set


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_ndjson_detail_path_serializes_windows_style_path_as_posix(
    tmp_path: Path,
    command: PipelineKindLiteral,
) -> None:
    """Processing NDJSON result paths should use POSIX separators in detail mode."""
    cfg: FrozenConfig = make_frozen_config()
    ctx: ProcessingContext = make_pipeline_context(path=tmp_path / "example.py", cfg=cfg)

    # The production attribute is a concrete Path, but this contract test needs
    # to exercise Windows-native `str(path)` behavior on every host platform.
    processing_result: ProcessingResult = replace(
        ProcessingResult.from_context(ctx),
        path=cast("Path", _WindowsStylePath()),
    )

    records: list[dict[str, object]] = list(
        iter_processing_results_stream_ndjson_records(
            meta=_machine_meta(),
            config=cfg,
            resolved_toml=_empty_resolved_toml_sources(),
            events=iter_machine_processing_stream([processing_result], command=command),
            summary_mode=False,
        )
    )

    result_records: list[dict[str, object]] = [
        record for record in records if record.get("kind") == "result"
    ]
    assert len(result_records) == 1

    result_obj: object | None = result_records[0].get("result")
    assert is_mapping(result_obj)
    result: dict[str, object] = as_object_dict(result_obj)

    assert result.get("path") == "C:/Repo/src/example.py"


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_ndjson_detail_symlink_input_serializes_canonical_target_path(
    tmp_path: Path,
    command: str,
) -> None:
    """Processing NDJSON detail paths should use the canonical processing target."""
    target: Path = tmp_path / "real" / "source.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('hello')\n", encoding="utf-8")
    link: Path = symlink_or_skip(tmp_path / "links" / "source-link.py", target)

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
            str(link.relative_to(tmp_path)),
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    result_records: list[dict[str, object]] = [
        record for record in records if record.get("kind") == "result"
    ]
    assert len(result_records) == 1

    result_obj: object | None = result_records[0].get("result")
    assert is_mapping(result_obj)
    result_payload: dict[str, object] = as_object_dict(result_obj)

    assert result_payload.get("path") == "real/source.py"


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_ndjson_summary_rows_do_not_use_legacy_key_label_shape(
    tmp_path: Path,
    command: str,
) -> None:
    """Ensure NDJSON summary rows use outcome/reason/count and not legacy key/label fields."""
    (tmp_path / "example.py").write_text(
        "#!/usr/bin/env python3\nprint('hi')\n",
        encoding="utf-8",
    )

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
            CliOpt.RESULTS_SUMMARY_MODE,
            ".",
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert records

    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")

    summary_records_found: int = 0
    for record in records:
        if record.get("kind") != "summary":
            continue

        summary_records_found += 1
        summary_obj: object | None = record.get("summary")
        assert is_mapping(summary_obj)
        summary: dict[str, object] = as_object_dict(summary_obj)

        assert "outcome" in summary
        assert "reason" in summary
        assert "count" in summary
        assert "key" not in summary
        assert "label" not in summary

    assert summary_records_found > 0


# Regression test: strict config warnings should remain machine-readable in NDJSON mode
@pytest.mark.parametrize("command", [CliCmd.CHECK, CliCmd.STRIP])
def test_processing_ndjson_strict_config_warning_emits_machine_diagnostics(
    tmp_path: Path,
    command: str,
) -> None:
    """Strict config warnings should remain machine-readable in NDJSON mode."""
    (tmp_path / "example.py").write_text("print('hi')\n", encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
            CliOpt.STRICT,
            CliOpt.INCLUDE_FILE_TYPES,
            "topmark:python,topmark:markdown",
            CliOpt.EXCLUDE_FILE_TYPES,
            "python,markdown",
            ".",
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
        assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")
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
        ("topmark:python", "topmark:markdown"),
    )
