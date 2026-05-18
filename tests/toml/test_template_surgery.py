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

from typing import TYPE_CHECKING

import pytest
import tomlkit

from topmark.constants import TOPMARK_END_MARKER
from topmark.core.errors import TemplateValidationError
from topmark.toml.template_surgery import ensure_pyproject_header
from topmark.toml.template_surgery import set_root_flag_in_template_text
from topmark.toml.template_surgery import validate_toml_for_config_init

if TYPE_CHECKING:
    from topmark.toml.template_surgery import TemplateEditResult


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
