# topmark:header:start
#
#   project      : TopMark
#   file         : test_machine_output.py
#   file_relpath : tests/cli/test_machine_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output contract tests for TopMark CLI commands.

This module verifies the JSON and NDJSON output emitted by TopMark’s
machine-readable modes (`--output-format json` and `--output-format ndjson`).

The tests serve as high-level contract checks to ensure that:

- Commands in the `topmark config` family emit a well-formed JSON object
  containing at least:
    - a `meta` block with `tool` and `version`,
    - a `config` payload.

- Processing commands such as `check` and `strip` emit machine output that also
  includes the `meta` block and follows the documented schema
  (see `docs/dev/machine-output.md`).

These tests intentionally avoid checking full schema content
(e.g. all config fields), focusing instead on structural stability and
the presence of required top-level keys. Detailed schema validation is
covered by lower-level tests in `topmark.cli_shared.machine_output`.

All CLI invocations are executed via Click’s `CliRunner`, using the
helpers in `tests.cli.conftest` to control the working directory and
assert exit codes.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pytest

from tests.cli.conftest import (
    assert_SUCCESS,
    assert_SUCCESS_or_WOULD_CHANGE,
    run_cli,
    run_cli_in,
)

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

# ----- JSON -----


def test_config_dump_json_includes_meta() -> None:
    """Ensure JSON output for `config dump` includes meta/tool/version.

    This is a high-level contract test for machine-readable output: the
    top-level JSON object must contain a `meta` block with `tool` and
    `version`, plus a `config` snapshot.
    """
    result: Result = run_cli(["config", "dump", "--output-format", "json"])
    assert_SUCCESS(result)

    payload: dict[str, Any] = json.loads(result.output)

    # Top-level keys
    assert "meta" in payload
    assert "config" in payload

    meta_obj = payload.get("meta")
    assert isinstance(meta_obj, dict)
    meta: dict[str, object] = cast("dict[str, object]", meta_obj)

    tool_obj = meta.get("tool")
    assert isinstance(tool_obj, str)
    assert tool_obj == "topmark"

    # Version should be a non-empty string
    version_obj = meta.get("version")
    assert isinstance(version_obj, str)
    assert version_obj != ""


@pytest.mark.parametrize("command", ["check", "strip"])
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
        [command, "--output-format", "json", "."],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, Any] = json.loads(result.output)
    assert "meta" in payload

    meta_obj = payload.get("meta")
    assert isinstance(meta_obj, dict)
    meta: dict[str, object] = cast("dict[str, object]", meta_obj)

    tool_obj = meta.get("tool")
    assert isinstance(tool_obj, str)
    assert tool_obj == "topmark"

    version_obj = meta.get("version")
    assert isinstance(version_obj, str)
    assert version_obj != ""


@pytest.mark.parametrize("command", ["check", "strip"])
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
        [command, "--output-format", "json", "."],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload_raw: object = json.loads(result.output)
    assert isinstance(payload_raw, dict)
    payload: dict[str, Any] = cast("dict[str, Any]", payload_raw)

    # Top-level wrapper keys
    assert "meta" in payload
    assert "config" in payload
    assert "config_diagnostics" in payload
    assert "results" in payload

    results_raw: object = payload["results"]
    assert isinstance(results_raw, list)
    results_list: list[object] = cast("list[object]", results_raw)
    assert results_list  # At least one result

    first_raw: object = results_list[0]
    assert isinstance(first_raw, dict)
    first: dict[str, Any] = cast("dict[str, Any]", first_raw)

    # Basic per-file keys
    for key in ("path", "file_type", "steps", "step_axes", "status", "views", "outcome"):
        assert key in first

    # steps: list of strings
    steps_raw: object = first["steps"]
    assert isinstance(steps_raw, list)
    steps: list[object] = cast("list[object]", steps_raw)
    assert steps
    for s in steps:
        assert isinstance(s, str)

    # step_axes: mapping step name -> list of axes
    step_axes_raw: object = first["step_axes"]
    assert isinstance(step_axes_raw, dict)
    step_axes: dict[str, Any] = cast("dict[str, Any]", step_axes_raw)
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
    assert isinstance(status_obj, dict)
    status: dict[str, Any] = cast("dict[str, Any]", status_obj)
    # We expect at least the "resolve" axis entry
    assert "resolve" in status
    resolve_status_obj = status["resolve"]
    assert isinstance(resolve_status_obj, dict)
    resolve_status: dict[str, Any] = cast("dict[str, Any]", resolve_status_obj)
    assert resolve_status.get("axis") == "resolve"
    assert isinstance(resolve_status.get("name"), str)
    assert isinstance(resolve_status.get("label"), str)

    # views: should be a mapping
    views_obj = first["views"]
    assert isinstance(views_obj, dict)

    # outcome: should be a mapping
    outcome_obj = first["outcome"]
    assert isinstance(outcome_obj, dict)


@pytest.mark.parametrize("command", ["check", "strip"])
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
        [command, "--output-format", "json", "--summary", "."],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload_obj: object = json.loads(result.output)
    assert isinstance(payload_obj, dict)
    payload: dict[str, Any] = cast("dict[str, Any]", payload_obj)

    # Top-level wrapper still includes meta/config/config_diagnostics
    assert "meta" in payload
    assert "config" in payload
    assert "config_diagnostics" in payload
    # Summary replaces the results array in summary-mode
    assert "summary" in payload

    summary_obj = payload["summary"]
    assert isinstance(summary_obj, dict)
    summary: dict[str, Any] = cast("dict[str, Any]", summary_obj)
    assert summary  # at least one bucket

    # Pick one bucket and validate its shape
    key, value_obj = next(iter(summary.items()))
    assert isinstance(key, str)
    assert isinstance(value_obj, dict)
    value: dict[str, Any] = cast("dict[str, Any]", value_obj)
    assert isinstance(value.get("count"), int)
    assert isinstance(value.get("label"), str)


# ----- NDJSON -----


def test_config_dump_ndjson_kinds() -> None:
    """Ensure NDJSON output for `config dump` emits a config record.

    Verifies that NDJSON output includes at least one `config` record. A
    `config_diagnostics` record may be added in the future, but is not required
    at present.
    """
    result: Result = run_cli(["config", "dump", "--output-format", "ndjson"])
    assert_SUCCESS(result)

    lines: list[str] = [line for line in result.output.splitlines() if line.strip()]
    assert lines  # at least two lines expected

    kinds: set[str] = set()
    for line in lines:
        record_obj: object = json.loads(line)
        assert isinstance(record_obj, dict)
        record: dict[str, Any] = cast("dict[str, Any]", record_obj)
        kind_obj = record.get("kind")
        assert isinstance(kind_obj, str)
        kinds.add(kind_obj)

    # For config dump we currently require a `config` record and allow,
    # but do not require, a `config_diagnostics` record.
    assert "config" in kinds
    assert kinds <= {"config", "config_diagnostics"}


@pytest.mark.parametrize("command", ["check", "strip"])
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
        [command, "--output-format", "ndjson", "--summary", "."],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    lines: list[str] = [line for line in result.output.splitlines() if line.strip()]
    assert lines

    kinds: list[str] = []
    for line in lines:
        record_obj: object = json.loads(line)
        assert isinstance(record_obj, dict)
        record: dict[str, Any] = cast("dict[str, Any]", record_obj)
        kind_obj = record.get("kind")
        assert isinstance(kind_obj, str)
        kinds.append(kind_obj)

        if kind_obj == "summary":
            key_obj = record.get("key")
            count_obj = record.get("count")
            label_obj = record.get("label")
            assert isinstance(key_obj, str)
            assert isinstance(count_obj, int)
            assert isinstance(label_obj, str)

    kinds_set: set[str] = set(kinds)
    assert "config" in kinds_set
    assert "config_diagnostics" in kinds_set
    assert "summary" in kinds_set
