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
  (see `docs/usage/machine-output.md`).

These tests intentionally avoid checking the full serialized config content,
focusing instead on structural stability, required top-level keys, provenance
layer shape, and defaults-layer ordering.

All CLI invocations are executed via Click's `CliRunner`, using the helpers in
`tests.cli.conftest` to assert exit codes and inspect machine-readable output.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import assert_ndjson_meta
from tests.helpers.ndjson import parse_ndjson_records
from tests.helpers.ndjson import parse_single_ndjson_record
from tests.helpers.ndjson import record_kinds
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.formats import OutputFormat
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def _write_minimal_config(path: Path) -> None:
    """Write a minimal valid TopMark config file for config-dump tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """\
            [fields]
            project = "Demo"

            [header]
            fields = ["project"]
            """
        ).lstrip(),
        encoding="utf-8",
    )


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
            OutputFormat.JSON.value,
        ],
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    # Top-level keys
    assert "meta" in payload
    assert "config" in payload

    meta_obj: object | None = payload.get("meta")
    assert is_mapping(meta_obj)
    meta: dict[str, object] = as_object_dict(meta_obj)

    tool_obj: object | None = meta.get("tool")
    assert isinstance(tool_obj, str)
    assert tool_obj == "topmark"

    # Version should be a non-empty string
    version_obj: object | None = meta.get("version")
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
            OutputFormat.JSON.value,
        ],
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    assert "meta" in payload
    assert "config_provenance" in payload
    assert "config" in payload

    provenance_obj: object | None = payload.get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    layers_obj: object | None = provenance.get("config_layers")
    assert is_any_list(layers_obj)
    layers: list[object] = layers_obj
    assert layers

    first_obj: object = layers[0]
    assert is_mapping(first_obj)
    first: dict[str, object] = as_object_dict(first_obj)

    assert isinstance(first.get("origin"), str)
    assert isinstance(first.get("kind"), str)
    assert isinstance(first.get("precedence"), int)

    toml_obj: object | None = first.get("toml")
    assert is_mapping(toml_obj)


def test_config_dump_json_show_layers_includes_discovery_anchor(tmp_path: Path) -> None:
    """JSON config provenance should expose the resolved discovery anchor."""
    workspace: Path = tmp_path / "workspace"
    config_file: Path = workspace / "topmark.toml"
    _write_minimal_config(config_file)

    result: Result = run_cli_in(
        workspace,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    provenance_obj: object | None = payload.get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    discovery_anchor_obj: object | None = provenance.get("discovery_anchor")
    assert isinstance(discovery_anchor_obj, str)
    assert discovery_anchor_obj == workspace.resolve().as_posix()


def test_config_dump_json_show_layers_resolves_symlinked_discovery_anchor(
    tmp_path: Path,
) -> None:
    """Discovery-anchor provenance should use the resolved target for symlinked CWD."""
    real_workspace: Path = tmp_path / "real-workspace"
    config_file: Path = real_workspace / "topmark.toml"
    _write_minimal_config(config_file)

    linked_workspace: Path = tmp_path / "linked-workspace"
    try:
        linked_workspace.symlink_to(real_workspace, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable in this environment: {exc}")

    result: Result = run_cli_in(
        linked_workspace,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    provenance_obj: object | None = payload.get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    discovery_anchor_obj: object | None = provenance.get("discovery_anchor")
    assert isinstance(discovery_anchor_obj, str)
    assert discovery_anchor_obj == real_workspace.resolve().as_posix()


def test_config_dump_json_without_show_layers_omits_discovery_anchor(tmp_path: Path) -> None:
    """Default config snapshots should not mix provenance into `config`."""
    workspace: Path = tmp_path / "workspace"
    config_file: Path = workspace / "topmark.toml"
    _write_minimal_config(config_file)

    result: Result = run_cli_in(
        workspace,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)
    assert "config_provenance" not in payload

    config_obj: object | None = payload.get("config")
    assert is_mapping(config_obj)
    config: dict[str, object] = as_object_dict(config_obj)
    assert "discovery_anchor" not in config


def test_config_dump_json_show_layers_defaults_layer_shape() -> None:
    """Ensure JSON provenance starts with the built-in defaults layer."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    provenance_obj: object | None = payload.get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    layers_obj: object | None = provenance.get("config_layers")
    assert is_any_list(layers_obj)
    layers: list[object] = layers_obj
    assert layers

    first_obj: object = layers[0]
    assert is_mapping(first_obj)
    first: dict[str, object] = as_object_dict(first_obj)

    assert first.get("origin") == "<defaults>"
    assert first.get("kind") == "default"
    assert first.get("precedence") == 0

    toml_obj: object | None = first.get("toml")
    assert is_mapping(toml_obj)
    toml_fragment: dict[str, object] = as_object_dict(toml_obj)
    assert "config" in toml_fragment
    assert "writer" in toml_fragment


def test_config_dump_json_config_files_use_posix_paths_for_explicit_config(
    tmp_path: Path,
) -> None:
    """JSON config snapshots should serialize explicit config files POSIX-style."""
    config_file: Path = tmp_path / "workspace" / "topmark.toml"
    _write_minimal_config(config_file)

    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.CONFIG_FILES,
            str(config_file),
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    config_obj: object | None = payload.get("config")
    assert is_mapping(config_obj)
    config: dict[str, object] = as_object_dict(config_obj)

    files_obj: object | None = config.get("files")
    assert is_mapping(files_obj)
    files: dict[str, object] = as_object_dict(files_obj)

    config_files_obj: object | None = files.get("config_files")
    assert is_any_list(config_files_obj)
    assert config_file.as_posix() in config_files_obj


def test_config_dump_json_show_layers_uses_posix_paths_for_explicit_config_provenance(
    tmp_path: Path,
) -> None:
    """JSON config provenance should serialize explicit config paths POSIX-style."""
    config_file: Path = tmp_path / "workspace" / "topmark.toml"
    _write_minimal_config(config_file)

    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.CONFIG_FILES,
            str(config_file),
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
        ],
    )
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    provenance_obj: object | None = payload.get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    layers_obj: object | None = provenance.get("config_layers")
    assert is_any_list(layers_obj)

    matching_layers: list[dict[str, object]] = []
    for layer_obj in layers_obj:
        assert is_mapping(layer_obj)
        layer: dict[str, object] = as_object_dict(layer_obj)
        if layer.get("origin") == config_file.as_posix():
            matching_layers.append(layer)

    assert len(matching_layers) == 1
    layer = matching_layers[0]
    assert layer.get("scope_root") == config_file.parent.as_posix()


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
            OutputFormat.NDJSON.value,
        ],
    )
    assert_SUCCESS(result)

    record: dict[str, object] = parse_single_ndjson_record(result.output)

    kind_obj: object | None = record.get("kind")
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
            OutputFormat.NDJSON.value,
        ],
    )
    assert_SUCCESS(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert len(records) == 2
    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")

    assert record_kinds(records) == ["config_provenance", "config"]

    provenance_obj: object | None = records[0].get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    layers_obj: object | None = provenance.get("config_layers")
    assert is_any_list(layers_obj)
    assert layers_obj


def test_config_dump_ndjson_show_layers_includes_discovery_anchor(tmp_path: Path) -> None:
    """NDJSON config provenance should expose the resolved discovery anchor."""
    workspace: Path = tmp_path / "workspace"
    config_file: Path = workspace / "topmark.toml"
    _write_minimal_config(config_file)

    result: Result = run_cli_in(
        workspace,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
        ],
    )
    assert_SUCCESS(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert record_kinds(records) == ["config_provenance", "config"]

    provenance_obj: object | None = records[0].get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    discovery_anchor_obj: object | None = provenance.get("discovery_anchor")
    assert isinstance(discovery_anchor_obj, str)
    assert discovery_anchor_obj == workspace.resolve().as_posix()


def test_config_dump_ndjson_show_layers_defaults_layer_shape() -> None:
    """Ensure NDJSON provenance starts with the built-in defaults layer."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
        ],
    )
    assert_SUCCESS(result)

    records: list[dict[str, object]] = parse_ndjson_records(result.output)
    assert len(records) == 2
    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level="brief")

    first_record: dict[str, object] = records[0]

    assert first_record.get("kind") == "config_provenance"

    provenance_obj: object | None = first_record.get("config_provenance")
    assert is_mapping(provenance_obj)
    provenance: dict[str, object] = as_object_dict(provenance_obj)

    layers_obj: object | None = provenance.get("config_layers")
    assert is_any_list(layers_obj)
    layers: list[object] = layers_obj
    assert layers

    first_layer_obj: object = layers[0]
    assert is_mapping(first_layer_obj)
    first_layer: dict[str, object] = as_object_dict(first_layer_obj)

    assert first_layer.get("origin") == "<defaults>"
    assert first_layer.get("kind") == "default"
    assert first_layer.get("precedence") == 0

    toml_obj: object | None = first_layer.get("toml")
    assert is_mapping(toml_obj)
