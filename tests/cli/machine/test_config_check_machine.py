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

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import assert_ndjson_meta
from tests.helpers.ndjson import parse_ndjson_records
from tests.helpers.ndjson import record_kinds
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from click.testing import Result


def _write_config_with_staged_diagnostics(path: Path) -> None:
    """Write a config file that produces TOML, merged, and runtime warnings."""
    path.write_text(
        """
[config]
bogus = true

[files]
include_file_types = ["python", "python", "definitely-not-a-real-type"]
""".lstrip(),
        encoding="utf-8",
    )


def _extract_diagnostic_messages_from_ndjson(records: list[dict[str, object]]) -> list[str]:
    """Return machine diagnostic messages from NDJSON config-check output."""
    messages: list[str] = []
    for record in records:
        if record.get("kind") != "diagnostic":
            continue
        diagnostic_obj: object | None = record.get("diagnostic")
        assert is_mapping(diagnostic_obj)
        diagnostic: dict[str, object] = as_object_dict(diagnostic_obj)
        message_obj: object | None = diagnostic.get("message")
        assert isinstance(message_obj, str)
        messages.append(message_obj)
    return messages


def _find_first_matching_index(messages: list[str], predicate: Callable[[str], bool]) -> int:
    """Return the first message index that satisfies `predicate`."""
    for index, message in enumerate(messages):
        if predicate(message):
            return index
    raise AssertionError("Expected diagnostic message was not found")


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

    payload: dict[str, object] = parse_json_object(result.output)

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

    payload: dict[str, object] = parse_json_object(result.output)

    diagnostics_obj: object | None = payload.get("config_diagnostics")
    assert is_mapping(diagnostics_obj)
    diagnostics: dict[str, object] = as_object_dict(diagnostics_obj)

    assert "diagnostics" in diagnostics
    assert "diagnostic_counts" in diagnostics
    assert "strict_config_checking" not in diagnostics


def test_config_check_json_flattens_staged_diagnostics_into_payload(tmp_path: Path) -> None:
    """JSON diagnostics payload should expose flattened staged diagnostics."""
    config_file: Path = tmp_path / "topmark.toml"
    _write_config_with_staged_diagnostics(config_file)

    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            "--config",
            str(config_file),
            "--no-strict",
            CliOpt.OUTPUT_FORMAT,
            "json",
        ]
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    diagnostics_obj: object | None = payload.get("config_diagnostics")
    assert is_mapping(diagnostics_obj)
    diagnostics: dict[str, object] = as_object_dict(diagnostics_obj)

    entries_obj: object | None = diagnostics.get("diagnostics")
    assert is_any_list(entries_obj)

    entries: list[dict[str, object]] = []
    for entry_obj in entries_obj:
        entries.append(as_object_dict(entry_obj))

    messages: list[str] = []
    for entry in entries:
        message_obj: object | None = entry.get("message")
        assert isinstance(message_obj, str)
        messages.append(message_obj)

    assert any("[config]" in message and "unknown" in message.lower() for message in messages)
    assert any("Duplicate included file types found in config" in message for message in messages)
    assert any("Unknown included file types specified" in message for message in messages)


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

    payload: dict[str, object] = parse_json_object(result.output)

    config_check_summary_obj: object | None = payload.get("config_check")
    assert is_mapping(config_check_summary_obj)
    config_check_summary: dict[str, object] = as_object_dict(config_check_summary_obj)

    assert "command" in config_check_summary
    assert "ok" in config_check_summary
    assert "strict_config_checking" in config_check_summary


def test_config_check_json_uses_config_check_payload_not_legacy_summary_key() -> None:
    """Ensure JSON output uses `config_check` and not a legacy generic summary key."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ]
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    assert "config_check" in payload
    assert "summary" not in payload


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

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert len(records) >= 3

    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")

    kinds: list[str] = record_kinds(records)
    assert kinds[:3] == ["config", "config_diagnostics", "config_check"]
    assert all(kind == "diagnostic" for kind in kinds[3:])


def test_config_check_ndjson_flattens_staged_diagnostics_in_order(tmp_path: Path) -> None:
    """NDJSON diagnostics should preserve flattened staged diagnostic order."""
    config_file: Path = tmp_path / "topmark.toml"
    _write_config_with_staged_diagnostics(config_file)

    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            "--config",
            str(config_file),
            "--no-strict",
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ]
    )
    assert_SUCCESS(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")

    messages: list[str] = _extract_diagnostic_messages_from_ndjson(records)

    toml_index: int = _find_first_matching_index(
        messages,
        lambda message: "unknown" in message.lower() and "[config]" in message,
    )
    merged_index: int = _find_first_matching_index(
        messages,
        lambda message: "Duplicate included file types found in config" in message,
    )
    runtime_index: int = _find_first_matching_index(
        messages,
        lambda message: "Unknown included file types specified" in message,
    )

    assert toml_index < merged_index < runtime_index


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

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert len(records) >= 2

    record: dict[str, object] = records[1]

    assert record.get("kind") == "config_diagnostics"
    assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")

    diagnostics_obj: object | None = record.get("config_diagnostics")
    assert is_mapping(diagnostics_obj)
    diagnostics: dict[str, object] = as_object_dict(diagnostics_obj)

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

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert len(records) >= 3

    record: dict[str, object] = records[2]

    assert record.get("kind") == "config_check"
    assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")

    config_check_summary_obj: object | None = record.get("config_check")
    assert is_mapping(config_check_summary_obj)
    config_check_summary: dict[str, object] = as_object_dict(config_check_summary_obj)

    assert "strict_config_checking" in config_check_summary


def test_config_check_ndjson_third_record_uses_config_check_container_not_summary() -> None:
    """Ensure the third NDJSON record uses `config_check`, not a legacy summary container."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ]
    )
    assert_SUCCESS(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert len(records) >= 3

    record: dict[str, object] = records[2]

    assert record.get("kind") == "config_check"
    assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")

    assert "config_check" in record
    assert "summary" not in record
