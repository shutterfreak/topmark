# topmark:header:start
#
#   project      : TopMark
#   file         : test_template_surgery.py
#   file_relpath : tests/toml/test_template_surgery.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for presentation-oriented TOML template surgery."""

from __future__ import annotations

import pytest
import tomlkit
from tomlkit.exceptions import ParseError as TomlkitParseError

from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.errors import TemplateValidationError
from topmark.toml.template_surgery import TemplateEditResult
from topmark.toml.template_surgery import ensure_pyproject_header
from topmark.toml.template_surgery import set_root_flag_in_template_text
from topmark.toml.template_surgery import validate_toml_for_config_init


def _assert_valid_toml(text: str) -> None:
    """Assert that edited template text remains valid TOML."""
    tomlkit.parse(text)


def test_ensure_pyproject_header_inserts_after_topmark_header_block() -> None:
    """Pyproject header insertion should preserve the TopMark banner first."""
    source: str = (
        f"# topmark:header:start\n# h\n# {TOPMARK_END_MARKER}\n\n# Example config\n[config]\n"
    )

    result: TemplateEditResult = ensure_pyproject_header(source)

    assert result.changed is True
    assert result.text.startswith(
        "# topmark:header:start\n"
        "# h\n"
        f"# {TOPMARK_END_MARKER}\n"
        "\n"
        "[tool.topmark]\n"
        "\n"
        "# Example config\n"
    )
    _assert_valid_toml(result.text)


def test_ensure_pyproject_header_is_idempotent_for_real_header() -> None:
    """An existing real `[tool.topmark]` table should not be duplicated."""
    source: str = "[tool.topmark]\n\n[tool.topmark.config]\n"

    result: TemplateEditResult = ensure_pyproject_header(source)

    assert result.changed is False
    assert result.text == source


def test_ensure_pyproject_header_ignores_comment_mentions() -> None:
    """Comment mentions of `[tool.topmark]` should not count as real headers."""
    source: str = "# Use [tool.topmark] in pyproject.toml\n[config]\n"

    result: TemplateEditResult = ensure_pyproject_header(source)

    assert result.changed is True
    assert result.text.startswith("[tool.topmark]\n\n# Use [tool.topmark]")
    _assert_valid_toml(result.text)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("", "[tool.topmark]"),
        ("# starter", "[tool.topmark]\n\n# starter"),
        ("# starter\n", "[tool.topmark]\n\n# starter\n"),
    ],
)
def test_ensure_pyproject_header_handles_minimal_final_newline_states(
    source: str,
    expected: str,
) -> None:
    """Minimal inputs should remain parseable without changing EOF newline state."""
    result: TemplateEditResult = ensure_pyproject_header(source)

    assert result == TemplateEditResult(text=expected, changed=True)
    assert result.text.endswith("\n") is source.endswith("\n")
    _assert_valid_toml(result.text)


def test_ensure_pyproject_header_preserves_crlf_and_is_repeatable() -> None:
    """Insertion should preserve CRLF consistently and become idempotent."""
    source: str = "# preamble\r\n[config]\r\nstrict = false\r\n"

    first: TemplateEditResult = ensure_pyproject_header(source)
    second: TemplateEditResult = ensure_pyproject_header(first.text)

    assert "[tool.topmark]\r\n\r\n# preamble" in first.text
    assert "\n" not in first.text.replace("\r\n", "")
    assert second == TemplateEditResult(text=first.text, changed=False)
    _assert_valid_toml(first.text)


def test_ensure_pyproject_header_recognizes_indented_exact_header_only() -> None:
    """Whitespace is allowed, while child tables do not masquerade as the header."""
    existing: str = "  [tool.topmark] # owned\nkey = true\n"
    child_only: str = "[tool.topmark.config]\nstrict = false\n"

    assert ensure_pyproject_header(existing) == TemplateEditResult(
        text=existing,
        changed=False,
    )
    inserted: TemplateEditResult = ensure_pyproject_header(child_only)
    assert inserted.text.startswith("[tool.topmark]\n\n[tool.topmark.config]")
    _assert_valid_toml(inserted.text)


def test_ensure_pyproject_header_after_unterminated_owned_header() -> None:
    """Insertion after an EOF marker should separate lines without adding an EOF newline."""
    source: str = f"# topmark:header:start\n# {TOPMARK_END_MARKER}"

    result: TemplateEditResult = ensure_pyproject_header(source)

    assert result.text == f"# topmark:header:start\n# {TOPMARK_END_MARKER}\n[tool.topmark]"
    assert result.changed is True
    _assert_valid_toml(result.text)


def test_set_root_flag_plain_inserts_below_documented_anchor() -> None:
    """Plain templates should insert root under `[config]` near the example anchor."""
    source: str = '[config]\n# root = true\nproject = "Demo"\n'

    result: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=False,
        root=True,
    )

    assert result.changed is True
    assert result.text == '[config]\n# root = true\nroot = true\n\nproject = "Demo"\n'
    _assert_valid_toml(result.text)


def test_set_root_flag_plain_is_idempotent_when_root_exists() -> None:
    """Existing root flag in the correct table should be preserved unchanged."""
    source: str = '[config]\nroot = true\nproject = "Demo"\n'

    result: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=False,
        root=True,
    )

    assert result.changed is False
    assert result.text == source


def test_set_root_flag_plain_removes_only_config_root() -> None:
    """Disabling root should only remove the exact key in the target table."""
    source: str = "[config]\nroot = true\n\n[other]\nroot = true\n"

    result: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=False,
        root=False,
    )

    assert result.changed is True
    assert result.text == "[config]\n\n[other]\nroot = true\n"
    _assert_valid_toml(result.text)


def test_set_root_flag_plain_deduplicates_root_in_target_table() -> None:
    """Multiple root flags in the target table should collapse to the first one."""
    source: str = "[config]\nroot = true\nroot = true\n"

    result: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=False,
        root=True,
    )

    assert result.changed is True
    assert result.text == "[config]\nroot = true\n"
    _assert_valid_toml(result.text)


def test_set_root_flag_plain_fallback_inserts_after_header_block() -> None:
    """Plain fallback insertion should place `[config]` after the TopMark header."""
    source: str = (
        f'# topmark:header:start\n# h\n# {TOPMARK_END_MARKER}\n\n[header]\nproject = "Demo"\n'
    )

    result: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=False,
        root=True,
    )

    assert result.changed is True
    assert result.text.startswith(
        "# topmark:header:start\n"
        "# h\n"
        f"# {TOPMARK_END_MARKER}\n"
        "\n"
        "[config]\n"
        "root = true\n"
        "\n"
        "[header]\n"
    )
    _assert_valid_toml(result.text)


def test_set_root_flag_pyproject_inserts_under_tool_topmark_config() -> None:
    """Pyproject mode should use `[tool.topmark.config]` scope."""
    source: str = '[tool.topmark]\n\n[tool.topmark.header]\nproject = "Demo"\n'

    result: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=True,
        root=True,
    )

    assert result.changed is True
    assert result.text == (
        "[tool.topmark]\n"
        "\n"
        "[tool.topmark.config]\n"
        "root = true\n"
        "\n"
        "[tool.topmark.header]\n"
        'project = "Demo"\n'
    )
    _assert_valid_toml(result.text)


def test_set_root_flag_pyproject_removes_only_pyproject_config_root() -> None:
    """Pyproject root removal should not touch plain `[config]` root."""
    source: str = "[config]\nroot = true\n\n[tool.topmark.config]\nroot = true\n"

    result: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=True,
        root=False,
    )

    assert result.changed is True
    assert result.text == "[config]\nroot = true\n\n[tool.topmark.config]\n"
    _assert_valid_toml(result.text)


@pytest.mark.parametrize("for_pyproject", [False, True])
def test_set_root_flag_handles_empty_documents_without_final_newline(
    for_pyproject: bool,
) -> None:
    """Fallback insertion should produce minimal parseable TOML in either scope."""
    result: TemplateEditResult = set_root_flag_in_template_text(
        "",
        for_pyproject=for_pyproject,
        root=True,
    )

    header: str = "[tool.topmark.config]" if for_pyproject else "[config]"
    assert result == TemplateEditResult(text=f"{header}\nroot = true", changed=True)
    parsed: tomlkit.TOMLDocument = tomlkit.parse(result.text)
    config = parsed["tool"]["topmark"]["config"] if for_pyproject else parsed["config"]
    assert config["root"] is True


@pytest.mark.parametrize("for_pyproject", [False, True])
def test_set_root_flag_preserves_crlf_eof_and_repeated_operations(
    for_pyproject: bool,
) -> None:
    """Enable/disable cycles should preserve newline style and EOF state."""
    header: str = "[tool.topmark.config]" if for_pyproject else "[config]"
    source: str = f"{header}\r\n# root = true\r\nstrict = false"

    enabled: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=for_pyproject,
        root=True,
    )
    enabled_again: TemplateEditResult = set_root_flag_in_template_text(
        enabled.text,
        for_pyproject=for_pyproject,
        root=True,
    )
    disabled: TemplateEditResult = set_root_flag_in_template_text(
        enabled.text,
        for_pyproject=for_pyproject,
        root=False,
    )
    disabled_again: TemplateEditResult = set_root_flag_in_template_text(
        disabled.text,
        for_pyproject=for_pyproject,
        root=False,
    )

    assert "root = true\r\n" in enabled.text
    assert "\n" not in enabled.text.replace("\r\n", "")
    assert not enabled.text.endswith(("\n", "\r"))
    assert enabled_again == TemplateEditResult(text=enabled.text, changed=False)
    assert disabled_again == TemplateEditResult(text=disabled.text, changed=False)
    assert "# root = true" in disabled.text
    _assert_valid_toml(disabled.text)


def test_set_root_flag_uncomments_only_exact_owned_header_anchor() -> None:
    """Commented header/root anchors should retain nearby documentation."""
    source: str = (
        "# [config.extra]\n"
        "# [config]\n"
        "# Root stops parent discovery.\n"
        "# root = true\n"
        "\n"
        "[other]\n"
        "root = true\n"
    )

    result: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=False,
        root=True,
    )

    assert "# [config.extra]\n[config]\n# Root stops" in result.text
    assert result.text.count("root = true") == 3  # anchor, owned key, unrelated key
    parsed: tomlkit.TOMLDocument = tomlkit.parse(result.text)
    assert parsed["config"]["root"] is True
    assert parsed["other"]["root"] is True


def test_set_root_flag_targets_exact_table_and_similarly_named_keys() -> None:
    """Only the owned exact key in the exact target table should be edited."""
    source: str = (
        "[config.extra]\nroot = true\n\n"
        "[config]\nrooted = true\nroot = true\n\n"
        "[other]\nroot = true\n"
    )

    result: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=False,
        root=False,
    )

    parsed: tomlkit.TOMLDocument = tomlkit.parse(result.text)
    assert parsed["config"]["rooted"] is True
    assert "root" not in parsed["config"]
    assert parsed["config"]["extra"]["root"] is True
    assert parsed["other"]["root"] is True


def test_set_root_flag_handles_unterminated_minimal_target_table() -> None:
    """An EOF table header should gain only the newline needed for its root key."""
    source: str = "[config]"

    enabled: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=False,
        root=True,
    )
    disabled: TemplateEditResult = set_root_flag_in_template_text(
        enabled.text,
        for_pyproject=False,
        root=False,
    )

    assert enabled == TemplateEditResult(text="[config]\nroot = true", changed=True)
    assert disabled == TemplateEditResult(text=source, changed=True)
    _assert_valid_toml(enabled.text)


def test_set_root_flag_disable_without_owned_table_is_unchanged() -> None:
    """Disabling should not create a target table when none exists."""
    source: str = "[other]\nroot = true\n"

    result: TemplateEditResult = set_root_flag_in_template_text(
        source,
        for_pyproject=False,
        root=False,
    )

    assert result == TemplateEditResult(text=source, changed=False)


def test_validate_toml_for_config_init_accepts_plain_root_config() -> None:
    """Plain config-init validation should accept `[config].root = true`."""
    validate_toml_for_config_init(
        "[config]\nroot = true\n",
        for_pyproject=False,
        root_expected=True,
    )


def test_validate_toml_for_config_init_accepts_pyproject_root_config() -> None:
    """Pyproject config-init validation should accept nested root config."""
    validate_toml_for_config_init(
        "[tool.topmark]\n\n[tool.topmark.config]\nroot = true\n",
        for_pyproject=True,
        root_expected=True,
    )


def test_validate_toml_for_config_init_rejects_invalid_toml() -> None:
    """Invalid edited TOML should raise a template validation error."""
    with pytest.raises(TemplateValidationError, match="Invalid TOML produced"):
        validate_toml_for_config_init(
            "[config\n",
            for_pyproject=False,
            root_expected=False,
        )


def test_validate_toml_for_config_init_rejects_missing_pyproject_table() -> None:
    """Pyproject validation should require a real `[tool.topmark]` table."""
    with pytest.raises(TemplateValidationError, match=r"Expected pyproject-style output"):
        validate_toml_for_config_init(
            "# [tool.topmark]\n[config]\nroot = true\n",
            for_pyproject=True,
            root_expected=False,
        )


def test_validate_toml_for_config_init_rejects_missing_plain_root() -> None:
    """Plain root validation should fail if `[config].root` is absent."""
    with pytest.raises(TemplateValidationError, match=r"root = true"):
        validate_toml_for_config_init(
            '[config]\nproject = "Demo"\n',
            for_pyproject=False,
            root_expected=True,
        )


@pytest.mark.parametrize(
    ("toml_text", "for_pyproject"),
    [
        ("", False),
        ("[config]\nstrict = false\n", False),
        ("[tool.topmark]\n", True),
        ("[tool.topmark.config]\nstrict = false\n", True),
    ],
)
def test_validate_toml_for_config_init_accepts_shapes_without_expected_root(
    toml_text: str,
    for_pyproject: bool,
) -> None:
    """Root is optional, but pyproject output still requires its owner table."""
    validate_toml_for_config_init(
        toml_text,
        for_pyproject=for_pyproject,
        root_expected=False,
    )


@pytest.mark.parametrize(
    ("toml_text", "for_pyproject", "message"),
    [
        ('tool = "scalar"\n', True, r"\[tool\].*not a table"),
        ('[tool]\ntopmark = "scalar"\n', True, r"\[tool\.topmark\].*not a table"),
        ("[tool]\n", True, r"\[tool\.topmark\].*missing"),
        ("[tool.topmark]\n", True, r"tool\.topmark\.config.*missing"),
        (
            '[tool.topmark]\nconfig = "scalar"\n',
            True,
            r"\[tool\.topmark\.config\].*not a table",
        ),
        ("[tool.topmark.config]\n", True, r"root.*missing"),
        ("[tool.topmark.config]\nroot = false\n", True, r"not true"),
        ('config = "scalar"\n', False, r"\[config\].*not a table"),
        ("# [config]\n", False, r"\[config\].*table is missing"),
        ("[config]\n", False, r"root.*missing"),
        ("[config]\nroot = false\n", False, r"not true"),
    ],
)
def test_validate_toml_for_config_init_rejects_incompatible_shapes(
    toml_text: str,
    for_pyproject: bool,
    message: str,
) -> None:
    """Diagnostics should identify the missing or incompatible owned shape."""
    with pytest.raises(TemplateValidationError, match=message):
        validate_toml_for_config_init(
            toml_text,
            for_pyproject=for_pyproject,
            root_expected=True,
        )


def test_validate_toml_for_config_init_chains_parse_failure() -> None:
    """Template validation should retain the underlying TOML parse error."""
    with pytest.raises(TemplateValidationError) as exc_info:
        validate_toml_for_config_init(
            "[config\n",
            for_pyproject=False,
            root_expected=False,
        )

    assert isinstance(exc_info.value.__cause__, TomlkitParseError)
