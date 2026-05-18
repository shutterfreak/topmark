# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_dump_output.py
#   file_relpath : tests/cli/test_config_dump_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI config-dump output validity tests.

This module verifies that `topmark config dump` emits parseable TOML in human
output when verbose TOML block markers are requested. It also validates the
shape of layered provenance output produced by `--show-layers`.

These are output/provenance tests rather than pure exit-code contract tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import pytest
import tomlkit
from tomlkit.exceptions import ParseError as TomlkitParseError

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.constants import TOML_BLOCK_END
from topmark.core.constants import TOML_BLOCK_START
from topmark.toml.typing_guards import is_toml_table

if TYPE_CHECKING:
    from click.testing import Result
    from tomlkit.container import Container
    from tomlkit.items import Item


def _extract_toml_blocks(output: str) -> list[str]:
    """Return TOML snippets found between verbose TOML block markers."""
    blocks: list[str] = []
    start_idx: int = 0

    while True:
        begin: int = output.find(TOML_BLOCK_START, start_idx)
        if begin == -1:
            break
        end: int = output.find(TOML_BLOCK_END, begin)
        if end == -1:
            break

        block_lines: list[str] = output[begin:end].splitlines()[1:]
        blocks.append("\n".join(block_lines))
        start_idx = end + len(TOML_BLOCK_END)

    return blocks


def _parse_toml_block(block: str) -> tomlkit.TOMLDocument:
    """Parse a TOML block or fail the test with a useful message."""
    try:
        return tomlkit.loads(block)
    except TypeError as exc:
        pytest.fail(f"TypeError during TOML parsing: {exc}")
    except TomlkitParseError as exc:
        pytest.fail(f"TomlDecodeError: {exc}")


# --- Flattened config output ---


def test_config_dump_outputs_valid_flattened_toml_block() -> None:
    """`config dump -v --no-color` should emit one flattened TOML block."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.NO_COLOR_MODE,  # Strip ANSI formatting to allow parsing the generated TOML
            CliOpt.VERBOSE,  # Render the BEGIN and END markers
        ]
    )

    assert_SUCCESS(result)

    assert TOML_BLOCK_START in result.output
    assert TOML_BLOCK_END in result.output

    # Verbose human output should contain exactly one parseable config block.
    blocks: list[str] = _extract_toml_blocks(result.output)
    assert len(blocks) == 1

    parsed: tomlkit.TOMLDocument = _parse_toml_block(blocks[0])
    assert "fields" in parsed
    assert "header" in parsed


# --- Layered provenance output ---


def test_config_dump_show_layers_outputs_provenance_and_flattened_toml_blocks() -> None:
    """`config dump --show-layers` should emit provenance then flattened TOML."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.NO_COLOR_MODE,  # Strip ANSI formatting to allow parsing the generated TOML
            CliOpt.VERBOSE,  # Render the BEGIN and END markers
        ]
    )

    assert_SUCCESS(result)

    blocks: list[str] = _extract_toml_blocks(result.output)
    assert len(blocks) == 2

    provenance_doc: tomlkit.TOMLDocument = _parse_toml_block(blocks[0])
    flattened_doc: tomlkit.TOMLDocument = _parse_toml_block(blocks[1])

    assert "layers" in provenance_doc
    raw_layers: Item | Container = provenance_doc["layers"]
    assert isinstance(raw_layers, list)
    assert len(raw_layers) >= 1

    layers: list[Any] = list(raw_layers)

    first_layer = layers[0]
    assert is_toml_table(first_layer)

    assert "origin" in first_layer
    assert "kind" in first_layer
    assert "precedence" in first_layer
    assert "toml" in first_layer
    assert isinstance(first_layer["toml"], dict)
    assert "config" not in first_layer
    assert "source_options" not in first_layer

    assert "fields" in flattened_doc
    assert "header" in flattened_doc


def test_config_dump_show_layers_defaults_layer_has_expected_shape() -> None:
    """Layered provenance should export the built-in defaults layer first."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
        ]
    )

    assert_SUCCESS(result)

    blocks: list[str] = _extract_toml_blocks(result.output)
    assert len(blocks) == 2

    provenance_doc: tomlkit.TOMLDocument = _parse_toml_block(blocks[0])

    assert "layers" in provenance_doc
    raw_layers: Item | Container = provenance_doc["layers"]
    assert isinstance(raw_layers, list)
    assert len(raw_layers) >= 1

    layers: list[Any] = list(raw_layers)

    first_layer = layers[0]
    assert is_toml_table(first_layer)

    assert first_layer["origin"] == "<defaults>"
    assert first_layer["kind"] == "default"
    assert first_layer["precedence"] == 0

    toml_fragment = first_layer["toml"]
    assert is_toml_table(toml_fragment)
    assert "config" in toml_fragment
    assert "writer" in toml_fragment


def test_config_dump_show_layers_includes_non_default_toml_fragment_when_available() -> None:
    """Layered provenance should include non-default TOML fragments when available."""
    result: Result = run_cli(
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
        ]
    )

    assert_SUCCESS(result)

    blocks: list[str] = _extract_toml_blocks(result.output)
    assert len(blocks) == 2

    provenance_doc: tomlkit.TOMLDocument = _parse_toml_block(blocks[0])

    assert "layers" in provenance_doc
    raw_layers: Item | Container = provenance_doc["layers"]
    assert isinstance(raw_layers, list)
    assert len(raw_layers) >= 1

    layers: list[Any] = list(raw_layers)
    assert all(is_toml_table(x) for x in layers)

    non_default_layers: list[Any] = [layer for layer in layers if layer.get("kind") != "default"]
    if non_default_layers:
        first_non_default = non_default_layers[0]
        assert "toml" in first_non_default
        assert is_toml_table(first_non_default["toml"])
