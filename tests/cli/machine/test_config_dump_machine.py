# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_dump_machine.py
#   file_relpath : tests/cli/machine/test_config_dump_machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output contract tests for `topmark config dump`.

This module verifies the JSON and NDJSON output emitted by
`topmark config dump` when machine-readable output modes are enabled
(`--output-format json` and `--output-format ndjson`).

The tests serve as high-level contract checks to ensure that:

- `topmark config dump` emits a well-formed machine payload containing at least:
    - a `meta` block with `tool` and `version`,
    - a flattened `config` payload,
    - and, when `--show-layers` is used, a layered `config_provenance`
      payload before the flattened config;
- NDJSON output preserves the intended record ordering:
    - default mode emits only a `config` record,
    - `--show-layers` emits `config_provenance` first and `config` second;
- the output follows the documented machine schema
  (see `docs/dev/machine-output.md`).

These tests intentionally avoid checking the full serialized config content,
focusing instead on structural stability, required top-level keys, provenance
layer shape, and defaults-layer ordering.

All CLI invocations are executed via Click’s `CliRunner`, using the helpers in
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

# ----- JSON -----


def test_config_dump_json_includes_meta() -> None:
    """Ensure JSON output for `config dump` includes meta/tool/version.

    This is a high-level contract test for machine-readable output: the
    top-level JSON object must contain a `meta` block with `tool` and
    `version`, plus a `config` snapshot.
    """
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ],
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = json.loads(result.output)

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


def test_config_dump_json_show_layers_includes_config_provenance() -> None:
    """Ensure JSON output for `config dump --show-layers` includes config provenance."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ],
    )
    assert_SUCCESS(result)

    payload_obj: object = json.loads(result.output)
    assert isinstance(payload_obj, dict)
    payload: dict[str, object] = cast("dict[str, object]", payload_obj)

    assert "meta" in payload
    assert "config_provenance" in payload
    assert "config" in payload

    provenance_obj = payload.get("config_provenance")
    assert isinstance(provenance_obj, dict)
    provenance: dict[str, object] = cast("dict[str, object]", provenance_obj)

    layers_obj = provenance.get("config_layers")
    assert isinstance(layers_obj, list)
    layers: list[object] = cast("list[object]", layers_obj)
    assert layers

    first_obj: object = layers[0]
    assert isinstance(first_obj, dict)
    first: dict[str, object] = cast("dict[str, object]", first_obj)

    assert isinstance(first.get("origin"), str)
    assert isinstance(first.get("kind"), str)
    assert isinstance(first.get("precedence"), int)

    toml_obj = first.get("toml")
    assert isinstance(toml_obj, dict)


def test_config_dump_json_show_layers_defaults_layer_shape() -> None:
    """Ensure JSON provenance starts with the built-in defaults layer."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ],
    )
    assert_SUCCESS(result)

    payload_obj: object = json.loads(result.output)
    assert isinstance(payload_obj, dict)
    payload: dict[str, object] = cast("dict[str, object]", payload_obj)

    provenance_obj = payload.get("config_provenance")
    assert isinstance(provenance_obj, dict)
    provenance: dict[str, object] = cast("dict[str, object]", provenance_obj)

    layers_obj = provenance.get("config_layers")
    assert isinstance(layers_obj, list)
    layers: list[object] = cast("list[object]", layers_obj)
    assert layers

    first_obj: object = layers[0]
    assert isinstance(first_obj, dict)
    first: dict[str, object] = cast("dict[str, object]", first_obj)

    assert first.get("origin") == "<defaults>"
    assert first.get("kind") == "default"
    assert first.get("precedence") == 0

    toml_obj = first.get("toml")
    assert isinstance(toml_obj, dict)
    toml_fragment: dict[str, object] = cast("dict[str, object]", toml_obj)
    assert "config" in toml_fragment
    assert "writer" in toml_fragment


# ----- NDJSON -----


def test_config_dump_ndjson_kinds() -> None:
    """Ensure NDJSON output for `config dump` emits only a config record by default.

    Verifies that NDJSON output includes a `config` record. Provenance records
    are only expected when `--show-layers` is used.
    """
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ],
    )
    assert_SUCCESS(result)

    lines: list[str] = [line for line in result.output.splitlines() if line.strip()]
    assert lines

    kinds: set[str] = set()
    for line in lines:
        record_obj: object = json.loads(line)
        assert isinstance(record_obj, dict)
        record: dict[str, object] = cast("dict[str, object]", record_obj)
        kind_obj = record.get("kind")
        assert isinstance(kind_obj, str)
        kinds.add(kind_obj)

    assert kinds == {"config"}


def test_config_dump_ndjson_show_layers_kinds() -> None:
    """Ensure NDJSON output for `config dump --show-layers` emits provenance first."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ],
    )
    assert_SUCCESS(result)

    lines: list[str] = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) == 2

    records: list[dict[str, object]] = []
    for line in lines:
        record_obj: object = json.loads(line)
        assert isinstance(record_obj, dict)
        records.append(cast("dict[str, object]", record_obj))

    assert records[0].get("kind") == "config_provenance"
    assert records[1].get("kind") == "config"

    provenance_obj = records[0].get("config_provenance")
    assert isinstance(provenance_obj, dict)
    provenance: dict[str, object] = cast("dict[str, object]", provenance_obj)

    layers_obj = provenance.get("config_layers")
    assert isinstance(layers_obj, list)
    assert layers_obj


def test_config_dump_ndjson_show_layers_defaults_layer_shape() -> None:
    """Ensure NDJSON provenance starts with the built-in defaults layer."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ],
    )
    assert_SUCCESS(result)

    lines: list[str] = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) == 2

    first_record_obj: object = json.loads(lines[0])
    assert isinstance(first_record_obj, dict)
    first_record: dict[str, object] = cast("dict[str, object]", first_record_obj)

    assert first_record.get("kind") == "config_provenance"

    provenance_obj = first_record.get("config_provenance")
    assert isinstance(provenance_obj, dict)
    provenance: dict[str, object] = cast("dict[str, object]", provenance_obj)

    layers_obj = provenance.get("config_layers")
    assert isinstance(layers_obj, list)
    layers: list[object] = cast("list[object]", layers_obj)
    assert layers

    first_layer_obj: object = layers[0]
    assert isinstance(first_layer_obj, dict)
    first_layer: dict[str, object] = cast("dict[str, object]", first_layer_obj)

    assert first_layer.get("origin") == "<defaults>"
    assert first_layer.get("kind") == "default"
    assert first_layer.get("precedence") == 0

    toml_obj = first_layer.get("toml")
    assert isinstance(toml_obj, dict)
