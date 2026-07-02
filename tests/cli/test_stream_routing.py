# topmark:header:start
#
#   project      : TopMark
#   file         : test_stream_routing.py
#   file_relpath : tests/cli/test_stream_routing.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI stdout/stderr stream-routing contract tests.

These tests pin the architectural split reviewed for GitHub issue 207:
primary command payloads are emitted on STDOUT, while diagnostics and
signaling that must not pollute payloads are emitted on STDERR.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_SUCCESS_or_WOULD_CHANGE
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import parse_ndjson_records
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.streaming import select_exit_code
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import OutputFormat

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param([CliCmd.VERSION], id="version-text"),
        pytest.param(
            [CliCmd.VERSION, CliOpt.OUTPUT_FORMAT, OutputFormat.JSON.value],
            id="version-json",
        ),
        pytest.param(
            [CliCmd.CONFIG, CliCmd.CONFIG_DEFAULTS],
            id="config-defaults-text",
        ),
        pytest.param(
            [CliCmd.CONFIG, CliCmd.CONFIG_DEFAULTS, CliOpt.OUTPUT_FORMAT, OutputFormat.JSON.value],
            id="config-defaults-json",
        ),
        pytest.param(
            [
                CliCmd.REGISTRY,
                CliCmd.REGISTRY_FILETYPES,
                CliOpt.OUTPUT_FORMAT,
                OutputFormat.JSON.value,
            ],
            id="registry-filetypes-json",
        ),
    ],
)
def test_content_commands_emit_payload_on_stdout_without_stderr(argv: list[str]) -> None:
    """Content-oriented commands should keep their normal payload on STDOUT."""
    result: Result = run_cli(argv)

    assert_SUCCESS(result)
    assert result.stdout
    assert result.stderr == ""


def test_processing_machine_summary_diff_keeps_stdout_parseable_and_warns_on_stderr(
    tmp_path: Path,
) -> None:
    """Machine summaries keep STDOUT parseable while diff suppression warns on STDERR."""
    path: Path = tmp_path / "example.py"
    path.write_text('print("hello")\n', encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.RENDER_DIFF,
            CliOpt.RESULTS_SUMMARY_MODE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            path.name,
        ],
    )

    assert_SUCCESS_or_WOULD_CHANGE(result)
    parse_json_object(result.stdout)
    assert "--diff does not emit per-file diff payloads" in result.stderr
    assert "Note:" not in result.stdout


def test_human_diff_routes_report_to_stderr_and_diff_payload_to_stdout(tmp_path: Path) -> None:
    """Human `--diff` reserves STDOUT for unified diff payloads."""
    path: Path = tmp_path / "example.py"
    path.write_text('print("hello")\n', encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.RENDER_DIFF, path.name],
    )

    assert_SUCCESS_or_WOULD_CHANGE(result)
    assert result.stdout.startswith(f"--- {path.name} (current)\t")
    assert f"\n+++ {path.name} (updated)\t" in result.stdout
    assert TOPMARK_START_MARKER in result.stdout
    assert "TopMark" in result.stderr


def test_apply_stdin_content_routes_rewritten_file_to_stdout_and_report_to_stderr() -> None:
    """Apply mode for content-on-STDIN keeps rewritten content isolated on STDOUT."""
    result: Result = run_cli(
        [CliCmd.CHECK, CliOpt.APPLY_CHANGES, "-", CliOpt.STDIN_FILENAME, "x.py"],
        input_text='print("hello")\n',
    )

    assert_SUCCESS(result)
    assert TOPMARK_START_MARKER in result.stdout
    assert 'print("hello")' in result.stdout
    assert "x.py: python - inserted" in result.stderr


def test_probe_ndjson_payload_stays_on_stdout(tmp_path: Path) -> None:
    """Probe machine output emits parseable NDJSON on STDOUT without STDERR chatter."""
    path: Path = tmp_path / "example.py"
    path.write_text('print("hello")\n', encoding="utf-8")

    result: Result = run_cli_in(
        tmp_path,
        [CliCmd.PROBE, CliOpt.OUTPUT_FORMAT, OutputFormat.NDJSON.value, path.name],
    )

    assert_SUCCESS(result)
    records: list[dict[str, object]] = parse_ndjson_records(result.stdout)
    assert records
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("current", "candidate", "expected"),
    [
        pytest.param(
            None,
            ExitCode.PIPELINE_ERROR,
            ExitCode.PIPELINE_ERROR,
            id="empty-selects-candidate",
        ),
        pytest.param(
            ExitCode.IO_ERROR,
            ExitCode.PERMISSION_DENIED,
            ExitCode.PERMISSION_DENIED,
            id="higher-priority-candidate-wins",
        ),
        pytest.param(
            ExitCode.PERMISSION_DENIED,
            ExitCode.IO_ERROR,
            ExitCode.PERMISSION_DENIED,
            id="current-wins-over-lower-priority-candidate",
        ),
    ],
)
def test_processing_stream_exit_code_priority(
    current: ExitCode | None,
    candidate: ExitCode,
    expected: ExitCode,
) -> None:
    """CLI stream statistics should retain the highest-priority exit code."""
    assert select_exit_code(current, candidate) is expected
