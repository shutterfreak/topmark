# topmark:header:start
#
#   project      : TopMark
#   file         : test_surgery.py
#   file_relpath : tests/toml/test_surgery.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for structural TOML surgery helpers."""

from __future__ import annotations

import pytest
import tomlkit

from topmark.core.errors import TomlParseError
from topmark.core.errors import TomlSurgeryError
from topmark.toml.surgery import nest_toml_under_section
from topmark.toml.surgery import set_root_flag


def _assert_valid_toml(text: str) -> None:
    """Assert that edited TOML remains parseable."""
    tomlkit.parse(text)


def test_set_root_flag_plain_creates_config_table() -> None:
    """Plain mode should create `[config].root = true` when missing."""
    result: str = set_root_flag(
        'project = "Demo"\n',
        for_pyproject=False,
        root=True,
    )

    assert 'project = "Demo"\n' in result
    assert "[config]\nroot = true\n" in result
    _assert_valid_toml(result)


def test_set_root_flag_plain_removes_top_level_root() -> None:
    """Plain mode should migrate away from deprecated top-level root."""
    result: str = set_root_flag(
        'root = true\n\n[config]\nproject = "Demo"\n',
        for_pyproject=False,
        root=True,
    )

    assert result.count("root = true") == 1
    assert '[config]\nproject = "Demo"\nroot = true\n' in result
    _assert_valid_toml(result)


def test_set_root_flag_plain_removes_config_root_when_disabled() -> None:
    """Plain mode should remove `[config].root` when root is disabled."""
    result: str = set_root_flag(
        '[config]\nroot = true\nproject = "Demo"\n',
        for_pyproject=False,
        root=False,
    )

    assert "root" not in tomlkit.parse(result)["config"]
    assert 'project = "Demo"' in result
    _assert_valid_toml(result)


def test_set_root_flag_plain_rejects_scalar_config() -> None:
    """Plain mode should reject a non-table `config` key."""
    with pytest.raises(TomlSurgeryError, match="'config' exists but is not a TOML table"):
        set_root_flag(
            'config = "not-table"\n',
            for_pyproject=False,
            root=True,
        )


def test_set_root_flag_pyproject_creates_nested_tables() -> None:
    """Pyproject mode should create `tool.topmark.config.root`."""
    result: str = set_root_flag(
        'project = "Demo"\n',
        for_pyproject=True,
        root=True,
    )

    parsed: tomlkit.TOMLDocument = tomlkit.parse(result)
    assert parsed["tool"]["topmark"]["config"]["root"] is True
    assert 'project = "Demo"\n' in result
    _assert_valid_toml(result)


def test_set_root_flag_pyproject_moves_topmark_root_to_config() -> None:
    """Pyproject mode should remove deprecated `tool.topmark.root`."""
    result: str = set_root_flag(
        '[tool.topmark]\nroot = true\n\n[tool.topmark.config]\nproject = "Demo"\n',
        for_pyproject=True,
        root=True,
    )

    parsed: tomlkit.TOMLDocument = tomlkit.parse(result)
    assert "root" not in parsed["tool"]["topmark"]
    assert parsed["tool"]["topmark"]["config"]["root"] is True
    _assert_valid_toml(result)


def test_set_root_flag_pyproject_removes_config_root_when_disabled() -> None:
    """Pyproject mode should remove `tool.topmark.config.root` when disabled."""
    result: str = set_root_flag(
        '[tool.topmark.config]\nroot = true\nproject = "Demo"\n',
        for_pyproject=True,
        root=False,
    )

    parsed: tomlkit.TOMLDocument = tomlkit.parse(result)
    assert "root" not in parsed["tool"]["topmark"]["config"]
    assert parsed["tool"]["topmark"]["config"]["project"] == "Demo"
    _assert_valid_toml(result)


def test_set_root_flag_pyproject_rejects_scalar_tool() -> None:
    """Pyproject mode should reject a non-table `tool` key."""
    with pytest.raises(TomlSurgeryError, match="'tool' exists but is not a TOML table"):
        set_root_flag(
            'tool = "not-table"\n',
            for_pyproject=True,
            root=True,
        )


def test_set_root_flag_pyproject_rejects_scalar_tool_topmark() -> None:
    """Pyproject mode should reject a non-table `tool.topmark` key."""
    with pytest.raises(TomlSurgeryError, match="'tool.topmark' exists but is not a TOML table"):
        set_root_flag(
            '[tool]\ntopmark = "not-table"\n',
            for_pyproject=True,
            root=True,
        )


def test_set_root_flag_pyproject_rejects_scalar_tool_topmark_config() -> None:
    """Pyproject mode should reject a non-table `tool.topmark.config` key."""
    with pytest.raises(
        TomlSurgeryError,
        match="'tool.topmark.config' exists but is not a TOML table",
    ):
        set_root_flag(
            '[tool.topmark]\nconfig = "not-table"\n',
            for_pyproject=True,
            root=True,
        )


def test_set_root_flag_rejects_invalid_toml() -> None:
    """Invalid TOML should be reported as a TOML parse error."""
    with pytest.raises(TomlParseError, match="Error parsing TOML document"):
        set_root_flag(
            "[config\n",
            for_pyproject=False,
            root=True,
        )


def test_nest_toml_under_section_wraps_plain_keys() -> None:
    """Plain keyed content should be nested under the requested section."""
    result: str = nest_toml_under_section(
        'project = "Demo"\n',
        "tool.topmark",
    )

    assert result == '[tool.topmark]\nproject = "Demo"\n'
    parsed: tomlkit.TOMLDocument = tomlkit.parse(result)
    assert parsed["tool"]["topmark"]["project"] == "Demo"


def test_nest_toml_under_section_preserves_preamble_comments() -> None:
    """Preamble comments should remain after the injected wrapper header."""
    source: str = '# comment\n\nproject = "Demo"\n'

    result: str = nest_toml_under_section(source, "tool.topmark")

    assert result == '[tool.topmark]\n\n# comment\n\nproject = "Demo"\n'
    _assert_valid_toml(result)


def test_nest_toml_under_section_prefixes_table_headers() -> None:
    """Existing table headers should be qualified under the wrapper path."""
    source: str = 'project = "Demo"\n\n[files]\ninclude = ["src"]\n'

    result: str = nest_toml_under_section(source, "tool.topmark")

    assert "[tool.topmark]\n" in result
    assert "[tool.topmark.files]\n" in result
    assert "[files]\n" not in result
    parsed: tomlkit.TOMLDocument = tomlkit.parse(result)
    assert parsed["tool"]["topmark"]["files"]["include"] == ["src"]


def test_nest_toml_under_section_prefixes_array_table_headers() -> None:
    """Array table headers should be qualified under the wrapper path."""
    source: str = '[[processors]]\nname = "demo"\n'

    result: str = nest_toml_under_section(source, "tool.topmark")

    assert "[[tool.topmark.processors]]\n" in result
    parsed: tomlkit.TOMLDocument = tomlkit.parse(result)
    assert parsed["tool"]["topmark"]["processors"][0]["name"] == "demo"


def test_nest_toml_under_section_preserves_inline_header_comments() -> None:
    """Inline comments on table headers should be preserved while prefixing."""
    source: str = '[files] # keep me\ninclude = ["src"]\n'

    result: str = nest_toml_under_section(source, "tool.topmark")

    assert "[tool.topmark.files] # keep me\n" in result
    _assert_valid_toml(result)


def test_nest_toml_under_section_is_idempotent_for_exact_wrapper() -> None:
    """Already wrapped documents should not be wrapped again."""
    source: str = '[tool.topmark]\nproject = "Demo"\n'

    result: str = nest_toml_under_section(source, "tool.topmark")

    assert result == source


def test_nest_toml_under_section_rejects_empty_section_keys() -> None:
    """Empty dotted section paths should be rejected."""
    with pytest.raises(ValueError, match="at least one non-empty component"):
        nest_toml_under_section(
            'project = "Demo"\n',
            "...",
        )


def test_nest_toml_under_section_rejects_invalid_toml() -> None:
    """Invalid input TOML should raise a TOML parse error."""
    with pytest.raises(TomlParseError, match="Error parsing TOML document"):
        nest_toml_under_section(
            "[files\n",
            "tool.topmark",
        )
