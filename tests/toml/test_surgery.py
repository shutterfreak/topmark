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
from tomlkit.exceptions import ParseError as TomlkitParseError

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


def test_set_root_flag_chains_parse_error() -> None:
    """The public parse error should retain tomlkit's original failure."""
    with pytest.raises(TomlParseError) as exc_info:
        set_root_flag("[config\n", for_pyproject=False, root=True)

    assert isinstance(exc_info.value.__cause__, TomlkitParseError)


@pytest.mark.parametrize("for_pyproject", [False, True])
def test_set_root_flag_is_semantically_idempotent_and_preserves_comments(
    for_pyproject: bool,
) -> None:
    """Repeated edits should keep one owned root and unrelated presentation."""
    source: str = "# preamble\n\n[other]\nvalue = 1 # retained\n"

    first: str = set_root_flag(source, for_pyproject=for_pyproject, root=True)
    second: str = set_root_flag(first, for_pyproject=for_pyproject, root=True)

    assert tomlkit.parse(second).unwrap() == tomlkit.parse(first).unwrap()
    assert second.count("root = true") == 1
    assert "# preamble" in second
    assert "value = 1 # retained" in second


@pytest.mark.parametrize("for_pyproject", [False, True])
def test_set_root_flag_disable_removes_legacy_and_owned_root_only(
    for_pyproject: bool,
) -> None:
    """Disabling should migrate legacy root away without deleting other keys."""
    if for_pyproject:
        source = (
            "[tool.topmark]\nroot = true\nkeep = 1\n\n"
            "[tool.topmark.config]\nroot = true\nstrict = false\n"
        )
    else:
        source = "root = true\nkeep = 1\n\n[config]\nroot = true\nstrict = false\n"

    result: str = set_root_flag(source, for_pyproject=for_pyproject, root=False)
    parsed: tomlkit.TOMLDocument = tomlkit.parse(result)
    owner = parsed["tool"]["topmark"] if for_pyproject else parsed

    assert "root" not in owner
    assert "root" not in owner["config"]
    assert owner["keep"] == 1
    assert owner["config"]["strict"] is False


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


@pytest.mark.parametrize("section_keys", ["", ".", "tool.", ".tool", "tool..topmark"])
def test_nest_toml_under_section_rejects_any_empty_segment(section_keys: str) -> None:
    """Dotted wrapper paths must not silently discard empty components."""
    with pytest.raises(ValueError, match="no empty components"):
        nest_toml_under_section('project = "Demo"\n', section_keys)


def test_nest_toml_under_section_rejects_invalid_toml() -> None:
    """Invalid input TOML should raise a TOML parse error."""
    with pytest.raises(TomlParseError, match="Error parsing TOML document"):
        nest_toml_under_section(
            "[files\n",
            "tool.topmark",
        )


def test_nest_toml_under_section_preserves_header_like_strings_and_comments() -> None:
    """Only real table headers should be qualified."""
    source: str = (
        '# [commented] and """ is still only a comment\npattern = "[quoted]"\n'
        'example = """\n[not-a-table]\n"""\n\n'
        "[files] # real\ninclude = []\n"
        "# postamble [also-not-a-table]\n"
    )

    result: str = nest_toml_under_section(source, "tool.topmark")

    assert "# [commented]" in result
    assert 'pattern = "[quoted]"' in result
    assert "\n[not-a-table]\n" in result
    assert "[tool.topmark.files] # real" in result
    assert result.index("# [commented]") < result.index("# postamble")
    _assert_valid_toml(result)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("", "[tool.topmark]"),
        ("# comment", "[tool.topmark]\n\n# comment"),
        ("value = 1", "[tool.topmark]\nvalue = 1"),
    ],
)
def test_nest_toml_under_section_preserves_final_newline_state(
    source: str,
    expected: str,
) -> None:
    """Empty, comment-only, and minimal documents should have deterministic EOFs."""
    result: str = nest_toml_under_section(source, "tool.topmark")

    assert result == expected
    _assert_valid_toml(result)


def test_nest_toml_under_section_preserves_crlf_consistently() -> None:
    """Wrapper and rewritten table headers should use the input CRLF style."""
    source: str = "# comment\r\n\r\n[files]\r\ninclude = []\r\n"

    result: str = nest_toml_under_section(source, "tool.topmark")

    assert result.startswith("[tool.topmark]\r\n\r\n# comment")
    assert "[tool.topmark.files]\r\n" in result
    assert "\n" not in result.replace("\r\n", "")
    _assert_valid_toml(result)


def test_nest_toml_under_section_mixed_wrapper_is_not_treated_as_idempotent() -> None:
    """A wrapper plus unrelated top-level content is nested again as a whole."""
    source: str = "[tool.topmark]\nvalue = 1\n\n[other]\nvalue = 2\n"

    result: str = nest_toml_under_section(source, "tool.topmark")
    parsed: tomlkit.TOMLDocument = tomlkit.parse(result)

    assert result != source
    assert parsed["tool"]["topmark"]["tool"]["topmark"]["value"] == 1
    assert parsed["tool"]["topmark"]["other"]["value"] == 2


def test_nest_toml_under_section_chains_invalid_input_parse_error() -> None:
    """Malformed input should retain its tomlkit parse cause."""
    with pytest.raises(TomlParseError) as exc_info:
        nest_toml_under_section("[files\n", "tool.topmark")

    assert isinstance(exc_info.value.__cause__, TomlkitParseError)


def test_nest_toml_under_section_rejects_wrapper_that_cannot_render_as_toml() -> None:
    """A syntactically incompatible requested wrapper should fail conservatively."""
    with pytest.raises(TomlSurgeryError, match="Cannot nest TOML document") as exc_info:
        nest_toml_under_section("value = 1\n", "not a bare key")

    assert isinstance(exc_info.value.__cause__, TomlkitParseError)
