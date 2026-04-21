# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_defaults_machine.py
#   file_relpath : tests/cli/machine/test_config_defaults_machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output contract tests for `topmark config defaults`.

This module verifies the JSON and NDJSON output emitted by
`topmark config defaults` when machine-readable output modes are enabled
(`--output-format json` and `--output-format ndjson`).

The tests serve as high-level contract checks to ensure that:

- `topmark config defaults` emits a well-formed machine payload containing at
  least:
    - a `meta` block with `tool` and `version`,
    - a flattened `config` payload;
- NDJSON output emits only a `config` record for this command;
- the output follows the documented machine schema
  (see `docs/dev/machine-output.md`).

These tests intentionally avoid checking the full serialized config content,
focusing instead on structural stability, required top-level keys, and a few
representative default config sections.

All CLI invocations are executed via Click's `CliRunner`, using the helpers in
`tests.cli.conftest` to assert exit codes and inspect machine-readable output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import assert_ndjson_meta
from tests.helpers.ndjson import parse_single_ndjson_record
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_mapping

if TYPE_CHECKING:
    from click.testing import Result


def test_config_defaults_json_includes_meta_and_config() -> None:
    """Ensure JSON output for `config defaults` includes meta and config."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DEFAULTS,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ]
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    assert "meta" in payload
    assert "config" in payload
    assert "config_diagnostics" not in payload
    assert "config_provenance" not in payload

    meta_obj: object | None = payload.get("meta")
    assert is_mapping(meta_obj)
    meta: dict[str, object] = as_object_dict(meta_obj)
    assert meta.get("tool") == "topmark"
    assert isinstance(meta.get("version"), str)


def test_config_defaults_json_contains_known_default_sections() -> None:
    """Ensure JSON output for `config defaults` contains representative sections."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DEFAULTS,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ]
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    config_obj: object | None = payload.get("config")
    assert is_mapping(config_obj)
    config: dict[str, object] = as_object_dict(config_obj)

    assert "fields" in config
    assert "header" in config
    assert "formatting" in config


def test_config_defaults_ndjson_emits_only_config_record() -> None:
    """Ensure NDJSON output for `config defaults` emits only a config record."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DEFAULTS,
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ]
    )
    assert_SUCCESS(result)

    record: dict[str, object] = parse_single_ndjson_record(result.output)

    assert record.get("kind") == "config"
    assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")
    assert "meta" in record
    assert "config" in record
    assert "config_diagnostics" not in record
    assert "config_provenance" not in record
