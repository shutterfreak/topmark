# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_check_machine.py
#   file_relpath : tests/cli/machine/test_config_check_machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output contract tests for `topmark config check`.

This module verifies the JSON and NDJSON output emitted by
`topmark config check` when machine-readable output modes are enabled
(`--output-format json` and `--output-format ndjson`).

The tests serve as high-level contract checks to ensure that:

- `topmark config check` emits a well-formed machine payload containing at
  least:
    - a `meta` block with `tool` and `version`,
    - a flattened `config` payload,
    - a `config_diagnostics` payload,
    - and a `summary` payload;
- NDJSON output preserves the intended record ordering for config-check output;
- the output follows the documented machine schema
  (see `docs/dev/machine-output.md`).

These tests intentionally avoid checking the full serialized config content,
focusing instead on structural stability, required top-level keys, diagnostic
shape, and NDJSON record ordering.

All CLI invocations are executed via Click's `CliRunner`, using the helpers in
`tests.cli.conftest` to assert exit codes and inspect machine-readable output.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import cast

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from click.testing import Result


def test_config_check_json_includes_expected_top_level_keys() -> None:
    """Ensure JSON output for `config check` includes the expected payloads."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ]
    )
    assert_SUCCESS(result)

    payload_obj: object = json.loads(result.output)
    assert isinstance(payload_obj, dict)
    payload: dict[str, object] = cast("dict[str, object]", payload_obj)

    assert "meta" in payload
    assert "config" in payload
    assert "config_diagnostics" in payload
    assert "config_check" in payload
    assert "config_provenance" not in payload


def test_config_check_json_config_diagnostics_shape() -> None:
    """Ensure JSON config diagnostics expose diagnostics and count data only."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ]
    )
    assert_SUCCESS(result)

    payload_obj: object = json.loads(result.output)
    assert isinstance(payload_obj, dict)
    payload: dict[str, object] = cast("dict[str, object]", payload_obj)

    diagnostics_obj: object | None = payload.get("config_diagnostics")
    assert isinstance(diagnostics_obj, dict)
    diagnostics: dict[str, object] = cast("dict[str, object]", diagnostics_obj)

    assert "diagnostics" in diagnostics
    assert "diagnostic_counts" in diagnostics
    assert "strict_config_checking" not in diagnostics


def test_config_check_json_summary_shape() -> None:
    """Ensure JSON summary for `config check` exposes strictness naming."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ]
    )
    assert_SUCCESS(result)

    payload_obj: object = json.loads(result.output)
    assert isinstance(payload_obj, dict)
    payload: dict[str, object] = cast("dict[str, object]", payload_obj)

    config_check_summary_obj: object | None = payload.get("config_check")
    assert isinstance(config_check_summary_obj, dict)
    config_check_summary: dict[str, object] = cast("dict[str, object]", config_check_summary_obj)

    assert "command" in config_check_summary
    assert "ok" in config_check_summary
    assert "strict_config_checking" in config_check_summary


def test_config_check_ndjson_record_order() -> None:
    """Ensure NDJSON output for `config check` starts with the expected records."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ]
    )
    assert_SUCCESS(result)

    lines: list[str] = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) >= 3

    records: list[dict[str, object]] = []
    for line in lines:
        record_obj: object = json.loads(line)
        assert isinstance(record_obj, dict)
        records.append(cast("dict[str, object]", record_obj))

    assert records[0].get("kind") == "config"
    assert records[1].get("kind") == "config_diagnostics"
    assert records[2].get("kind") == "config_check"

    for record in records[3:]:
        assert record.get("kind") == "diagnostic"


def test_config_check_ndjson_config_diagnostics_record_shape() -> None:
    """Ensure NDJSON config diagnostics record exposes count data only."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ]
    )
    assert_SUCCESS(result)

    lines: list[str] = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) >= 2

    record_obj: object = json.loads(lines[1])
    assert isinstance(record_obj, dict)
    record: dict[str, object] = cast("dict[str, object]", record_obj)

    assert record.get("kind") == "config_diagnostics"

    diagnostics_obj: object | None = record.get("config_diagnostics")
    assert isinstance(diagnostics_obj, dict)
    diagnostics: dict[str, object] = cast("dict[str, object]", diagnostics_obj)

    assert "diagnostics" not in diagnostics
    assert "diagnostic_counts" in diagnostics
    assert "strict_config_checking" not in diagnostics


def test_config_check_ndjson_summary_record_uses_strict_config_checking() -> None:
    """Ensure NDJSON summary record uses stable strictness naming."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ]
    )
    assert_SUCCESS(result)

    lines: list[str] = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) >= 3

    record_obj: object = json.loads(lines[2])
    assert isinstance(record_obj, dict)
    record: dict[str, object] = cast("dict[str, object]", record_obj)

    assert record.get("kind") == "config_check"

    config_check_summary_obj: object | None = record.get("config_check")
    assert isinstance(config_check_summary_obj, dict)
    config_check_summary: dict[str, object] = cast("dict[str, object]", config_check_summary_obj)

    assert "strict_config_checking" in config_check_summary
