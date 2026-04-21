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

from typing import TYPE_CHECKING

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import assert_ndjson_meta
from tests.helpers.ndjson import parse_ndjson_records
from tests.helpers.ndjson import parse_single_ndjson_record
from tests.helpers.ndjson import record_kinds
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping

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

    payload: dict[str, object] = parse_json_object(result.output)

    # Top-level keys
    assert "meta" in payload
    assert "config" in payload

    meta_obj = payload.get("meta")
    assert is_mapping(meta_obj)
    meta: dict[str, object] = as_object_dict(meta_obj)

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

    payload: dict[str, object] = parse_json_object(result.output)

    assert "meta" in payload
    assert "config_provenance" in payload
    assert "config" in payload

    provenance_obj = payload.get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    layers_obj = provenance.get("config_layers")
    assert is_any_list(layers_obj)
    layers: list[object] = layers_obj
    assert layers

    first_obj: object = layers[0]
    assert is_mapping(first_obj)
    first: dict[str, object] = as_object_dict(first_obj)

    assert isinstance(first.get("origin"), str)
    assert isinstance(first.get("kind"), str)
    assert isinstance(first.get("precedence"), int)

    toml_obj = first.get("toml")
    assert is_mapping(toml_obj)


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

    payload: dict[str, object] = parse_json_object(result.output)

    provenance_obj = payload.get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    layers_obj = provenance.get("config_layers")
    assert is_any_list(layers_obj)
    layers: list[object] = layers_obj
    assert layers

    first_obj: object = layers[0]
    assert is_mapping(first_obj)
    first: dict[str, object] = as_object_dict(first_obj)

    assert first.get("origin") == "<defaults>"
    assert first.get("kind") == "default"
    assert first.get("precedence") == 0

    toml_obj = first.get("toml")
    assert is_mapping(toml_obj)
    toml_fragment: dict[str, object] = as_object_dict(toml_obj)
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

    record: dict[str, object] = parse_single_ndjson_record(result.output)

    kind_obj = record.get("kind")
    assert isinstance(kind_obj, str)
    assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")
    kinds: set[str] = {kind_obj}

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

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert len(records) == 2
    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")

    assert record_kinds(records) == ["config_provenance", "config"]

    provenance_obj = records[0].get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    layers_obj = provenance.get("config_layers")
    assert is_any_list(layers_obj)
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

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert len(records) == 2
    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")

    first_record: dict[str, object] = records[0]

    assert first_record.get("kind") == "config_provenance"

    provenance_obj = first_record.get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    layers_obj = provenance.get("config_layers")
    assert is_any_list(layers_obj)
    layers: list[object] = layers_obj
    assert layers

    first_layer_obj: object = layers[0]
    assert is_mapping(first_layer_obj)
    first_layer: dict[str, object] = as_object_dict(first_layer_obj)

    assert first_layer.get("origin") == "<defaults>"
    assert first_layer.get("kind") == "default"
    assert first_layer.get("precedence") == 0

    toml_obj = first_layer.get("toml")
    assert is_mapping(toml_obj)
