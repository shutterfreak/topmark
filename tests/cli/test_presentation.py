# topmark:header:start
#
#   project      : TopMark
#   file         : test_presentation.py
#   file_relpath : tests/cli/test_presentation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI presentation helper contract tests."""

from __future__ import annotations

from topmark.cli.presentation import Theme
from topmark.cli.presentation import maybe_style
from topmark.cli.presentation import no_style_for_role
from topmark.cli.presentation import rich_styler
from topmark.cli.presentation import style_for_role
from topmark.core.presentation import StyleRole


def test_theme_uses_override_before_base_mapping() -> None:
    """Theme lookup should prefer explicit overrides over base stylers."""
    theme = Theme(
        base={StyleRole.ERROR: lambda text: f"base:{text}"},
        overrides={StyleRole.ERROR: lambda text: f"override:{text}"},
    )

    assert theme.styler_for(StyleRole.ERROR)("boom") == "override:boom"


def test_theme_falls_back_to_identity_styler_for_unknown_role() -> None:
    """Theme lookup should return a no-op styler when a role is unmapped."""
    theme = Theme(base={})

    styler = theme.styler_for(StyleRole.INFO)

    assert styler is no_style_for_role
    assert styler("plain") == "plain"


def test_style_for_role_returns_identity_when_styling_disabled() -> None:
    """Disabled styling should bypass the theme and return the no-op styler."""
    theme = Theme(base={StyleRole.ERROR: lambda text: f"styled:{text}"})

    styler = style_for_role(StyleRole.ERROR, styled=False, theme=theme)

    assert styler is no_style_for_role
    assert styler("plain") == "plain"


def test_maybe_style_returns_original_text_when_styling_disabled() -> None:
    """Conditional styling should not call the styler when styling is disabled."""

    def failing_styler(text: str) -> str:
        raise AssertionError(f"styler should not be called for {text!r}")

    assert maybe_style("plain", styler=failing_styler, styled=False) == "plain"


def test_maybe_style_applies_styler_when_styling_enabled() -> None:
    """Conditional styling should delegate to the provided styler when enabled."""
    assert maybe_style("plain", styler=lambda text: f"styled:{text}", styled=True) == (
        "styled:plain"
    )


def test_rich_styler_emits_ansi_when_rendering_style() -> None:
    """Rich stylers should keep ANSI generation inside the CLI adapter."""
    rendered: str = rich_styler("bold red")("alert")

    assert "alert" in rendered
    assert "\x1b[" in rendered
