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
  (see `docs/dev/machine-output.md`).

These tests intentionally avoid checking full schema content
(e.g. every per-axis status field), focusing instead on structural stability,
required top-level keys, and representative nested shapes.

All CLI invocations are executed via Click’s `CliRunner`, using the helpers in
`tests.cli.conftest` to control the working directory and assert exit codes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS_or_WOULD_CHANGE
from tests.cli.conftest import run_cli_in
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import parse_ndjson_records
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

# ----- JSON -----


@pytest.mark.parametrize(
    "command",
    [
        CliCmd.CHECK,
        CliCmd.STRIP,
    ],
)
def test_processing_json_includes_meta(tmp_path: Path, command: str) -> None:
    """Ensure JSON machine output for `check` / `strip` includes meta/tool/version.

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
            "json",
            ".",
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, object] = parse_json_object(result.output)
    assert "meta" in payload

    meta_obj = payload.get("meta")
    assert is_mapping(meta_obj)
    meta: dict[str, object] = as_object_dict(meta_obj)

    tool_obj = meta.get("tool")
    assert isinstance(tool_obj, str)
    assert tool_obj == "topmark"

    version_obj = meta.get("version")
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
    follow the documented machine-output schema (see `docs/dev/machine-output.md`).
    This focuses on structural stability (keys and types) rather than exact
    labels or counts and applies equally to `check` and `strip`.
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
            "json",
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
        "views",
        "outcome",
    ):
        assert key in first

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
    status_obj = first["status"]
    assert is_mapping(status_obj)
    status: dict[str, object] = as_object_dict(status_obj)
    # We expect at least the "resolve" axis entry
    assert "resolve" in status
    resolve_status_obj = status["resolve"]
    assert is_mapping(resolve_status_obj)
    resolve_status: dict[str, object] = as_object_dict(resolve_status_obj)
    assert resolve_status.get("axis") == "resolve"
    assert isinstance(resolve_status.get("name"), str)
    assert isinstance(resolve_status.get("label"), str)

    # views: should be a mapping
    views_obj = first["views"]
    assert is_mapping(views_obj)

    # outcome: should be a mapping
    outcome_obj = first["outcome"]
    assert is_mapping(outcome_obj)


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
            "json",
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

    summary_obj = payload["summary"]
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
            "json",
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
            "ndjson",
            CliOpt.RESULTS_SUMMARY_MODE,
            ".",
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert records

    kinds: list[str] = []
    for record in records:
        kind_obj = record.get("kind")
        assert isinstance(kind_obj, str)
        kinds.append(kind_obj)

        if kind_obj == "summary":
            summary_obj = record.get("summary")
            assert is_mapping(summary_obj)
            summary: dict[str, object] = as_object_dict(summary_obj)

            outcome_obj = summary.get("outcome")
            reason_obj = summary.get("reason")
            count_obj = summary.get("count")
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
            "ndjson",
            CliOpt.RESULTS_SUMMARY_MODE,
            ".",
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert records

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
