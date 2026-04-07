# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_init_machine.py
#   file_relpath : tests/cli/machine/test_config_init_machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output contract tests for `topmark config init`.

This module verifies the JSON and NDJSON output emitted by
`topmark config init` when machine-readable output modes are enabled
(`--output-format json` and `--output-format ndjson`).

The tests serve as high-level contract checks to ensure that:

- `topmark config init` emits a well-formed machine payload containing at
  least:
    - a `meta` block with `tool` and `version`,
    - a flattened `config` payload;
- NDJSON output emits only a `config` record for this command;
- the output follows the documented machine schema
  (see `docs/dev/machine-output.md`).

These tests intentionally avoid checking the full serialized config content,
focusing instead on structural stability, required top-level keys, and the fact
that machine output is a config snapshot rather than the annotated example TOML
resource used in human-facing output.

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


def test_config_init_json_includes_meta_and_config() -> None:
    """Ensure JSON output for `config init` includes meta and config."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_INIT,
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
    assert "config_diagnostics" not in payload
    assert "config_provenance" not in payload

    meta_obj: object | None = payload.get("meta")
    assert isinstance(meta_obj, dict)
    meta: dict[str, object] = cast("dict[str, object]", meta_obj)
    assert meta.get("tool") == "topmark"
    assert isinstance(meta.get("version"), str)


def test_config_init_json_is_structured_config_snapshot() -> None:
    """Ensure JSON output for `config init` is a config payload, not raw template text."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_INIT,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ]
    )
    assert_SUCCESS(result)

    payload_obj: object = json.loads(result.output)
    assert isinstance(payload_obj, dict)
    payload: dict[str, object] = cast("dict[str, object]", payload_obj)

    config_obj: object | None = payload.get("config")
    assert isinstance(config_obj, dict)
    config: dict[str, object] = cast("dict[str, object]", config_obj)

    assert "fields" in config
    assert "header" in config
    assert "toml_text" not in config


def test_config_init_ndjson_emits_only_config_record() -> None:
    """Ensure NDJSON output for `config init` emits only a config record."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_INIT,
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ]
    )
    assert_SUCCESS(result)

    lines: list[str] = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) == 1

    record_obj: object = json.loads(lines[0])
    assert isinstance(record_obj, dict)
    record: dict[str, object] = cast("dict[str, object]", record_obj)

    assert record.get("kind") == "config"
    assert "meta" in record
    assert "config" in record
    assert "config_diagnostics" not in record
    assert "config_provenance" not in record
