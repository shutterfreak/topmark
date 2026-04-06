# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_dump_output.py
#   file_relpath : tests/cli/test_config_dump_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for `topmark config dump` output validity.

Ensures that running `topmark config dump`:

- Exits successfully (exit code 0).
- Prints markers `TOML_BLOCK_START` and `TOML_BLOCK_END` in human output.
- Produces valid TOML snippets between markers.
- Optionally emits a layered TOML provenance export before the final flattened
  config when `--show-layers` is used.
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
from topmark.constants import TOML_BLOCK_END
from topmark.constants import TOML_BLOCK_START
from topmark.toml.typing_guards import is_toml_table

if TYPE_CHECKING:
    from click.testing import Result
    from tomlkit.container import Container
    from tomlkit.items import Item


def _extract_toml_blocks(output: str) -> list[str]:
    """Return TOML blocks found between BEGIN/END markers in CLI output."""
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


def test_dump_config_outputs_valid_toml() -> None:
    """It should emit one valid flattened TOML block by default."""
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

    # Extract the TOML slice
    blocks: list[str] = _extract_toml_blocks(result.output)
    assert len(blocks) == 1

    try:
        parsed: tomlkit.TOMLDocument = tomlkit.loads(blocks[0])
        assert "fields" in parsed
        assert "header" in parsed
    except TypeError as e:
        # If an exception is caught, use pytest.fail() to fail the test explicitly.
        # You can include the exception details in the message for better debugging.
        pytest.fail(f"TypeError during TOML parsing: {e}")
    except TomlkitParseError as e:
        # Fail the test if the TOML decoding fails.
        pytest.fail(f"TomlDecodeError: {e}")


def test_dump_config_show_layers_outputs_two_valid_toml_blocks() -> None:
    """It should emit layered provenance TOML followed by flattened TOML."""
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

    try:
        provenance_doc: tomlkit.TOMLDocument = tomlkit.loads(blocks[0])
        flattened_doc: tomlkit.TOMLDocument = tomlkit.loads(blocks[1])

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
    except TypeError as e:
        # If an exception is caught, use pytest.fail() to fail the test explicitly.
        # You can include the exception details in the message for better debugging.
        pytest.fail(f"TypeError during TOML parsing: {e}")
    except TomlkitParseError as e:
        # Fail the test if the TOML decoding fails.
        pytest.fail(f"TomlDecodeError: {e}")


def test_dump_config_show_layers_defaults_layer_has_expected_shape() -> None:
    """It should export the built-in defaults layer first in provenance output."""
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

    try:
        provenance_doc: tomlkit.TOMLDocument = tomlkit.loads(blocks[0])

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
    except TypeError as e:
        pytest.fail(f"TypeError during TOML parsing: {e}")
    except TomlkitParseError as e:
        pytest.fail(f"TomlDecodeError: {e}")


def test_dump_config_show_layers_includes_non_default_toml_fragment() -> None:
    """It should expose at least one non-default source-local TOML fragment when present."""
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

    try:
        provenance_doc: tomlkit.TOMLDocument = tomlkit.loads(blocks[0])

        assert "layers" in provenance_doc
        raw_layers: Item | Container = provenance_doc["layers"]
        assert isinstance(raw_layers, list)
        assert len(raw_layers) >= 1

        layers: list[Any] = list(raw_layers)
        assert all(is_toml_table(x) for x in layers)

        non_default_layers: list[Any] = [
            layer for layer in layers if layer.get("kind") != "default"
        ]
        if non_default_layers:
            first_non_default = non_default_layers[0]
            assert "toml" in first_non_default
            assert is_toml_table(first_non_default["toml"])
    except TypeError as e:
        pytest.fail(f"TypeError during TOML parsing: {e}")
    except TomlkitParseError as e:
        pytest.fail(f"TomlDecodeError: {e}")
