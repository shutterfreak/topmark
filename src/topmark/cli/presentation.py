# topmark:header:start
#
#   project      : TopMark
#   file         : presentation.py
#   file_relpath : src/topmark/cli/presentation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI presentation layer for semantic styling.

This module maps backend-agnostic semantic style roles
([`StyleRole`][topmark.core.presentation.StyleRole]) to concrete terminal styling callables
(currently backed by Rich).

Design goals:
    * Keep all ANSI / terminal styling confined to the CLI layer.
    * Centralize the mapping from semantic roles → concrete styles.
    * Allow theming and stackable style overrides.
    * Keep core and rendering layers free of presentation backends.

Key concepts
------------

- `StyleRole`: Semantic meaning (ERROR, WARNING, CHANGED, etc.).
- `Theme`: A mapping from `StyleRole` to a concrete text styler.
- `DEFAULT_THEME`: The built-in theme used by default.
- `style_for_role(role, theme=...)`: Resolve a styler for a role.

Theme and overrides
-------------------

Themes support **stackable overrides**. A `Theme` consists of:

    - `base`: The default mapping from `StyleRole` → styler.
    - `overrides`: Optional per-role overrides.

Lookup order:

    overrides → base → no-op (identity function)

Example: custom theme with overrides
------------------------------------

```py
from topmark.cli.presentation import DEFAULT_THEME
from topmark.cli.presentation import Theme
from topmark.cli.presentation import rich_styler
from topmark.cli.presentation import style_for_role
from topmark.core.presentation import StyleRole

custom_theme = Theme(
    base=DEFAULT_THEME.base,
    overrides={
        StyleRole.ERROR: rich_styler("bold white on red"),
        StyleRole.WARNING: rich_styler("yellow"),
    },
)

styler = style_for_role(StyleRole.ERROR, theme=custom_theme)
print(styler("Something went wrong"))
```

Stacking overrides
------------------

Overrides can be layered by reusing the same base mapping and adding new
override dictionaries:

```py
soft_theme = Theme(
    base=DEFAULT_THEME.base,
    overrides={
        StyleRole.CHANGED: rich_styler("cyan"),
    },
)

minimal_theme = Theme(
    base=soft_theme.base,
    overrides={
        StyleRole.ERROR: rich_styler("red"),
    },
)
```

This design keeps styling flexible while maintaining a single semantic source of truth(`StyleRole`)
across the application.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final
from typing import TypeAlias

from rich.console import Console as RichConsole
from rich.text import Text

from topmark.core.presentation import StyleRole

TextStyler: TypeAlias = Callable[[str], str]
"""Callable which styles a str."""

_RICH_CONSOLE: Final[RichConsole] = RichConsole(
    color_system="standard",
    force_terminal=True,
    legacy_windows=False,
    no_color=False,
    soft_wrap=True,
    width=120,
)


def rich_styler(style: str) -> TextStyler:
    """Return a `TextStyler` backed by Rich.

    The returned callable preserves the existing TopMark presentation contract:
    callers pass a plain string and receive a string containing terminal styling
    sequences. Rich renderables remain confined to this CLI adapter module.

    This helper is intended for programmatic theme definitions and test-specific
    theme overrides. It is not a user-facing configuration API; serialized theme
    configuration should be designed separately if TopMark adds configurable
    palettes in the future.

    Args:
        style: Rich style expression, such as `"bold red"` or `"cyan dim"`.

    Returns:
        A callable that renders text using the requested Rich style.
    """

    def apply_style(text: str) -> str:
        rich_text = Text(text, style=style)
        with _RICH_CONSOLE.capture() as capture:
            _RICH_CONSOLE.print(rich_text, end="")
        return capture.get()

    return apply_style


def no_style_for_role(s: str) -> str:
    """Return string verbatim (no-op)."""
    return s


DEFAULT_STYLE_ROLE_MAPPING: dict[StyleRole, TextStyler] = {
    # Severities
    StyleRole.INFO: rich_styler("blue"),
    StyleRole.WARNING: rich_styler("bright_yellow"),
    StyleRole.ERROR: rich_styler("bold bright_red"),
    # Generic outcomes / states
    StyleRole.OK: rich_styler("green"),
    StyleRole.MUTED: rich_styler("grey50"),
    StyleRole.EMPHASIS: rich_styler("bold"),
    StyleRole.ITALIC: rich_styler("italic"),
    # Change semantics
    StyleRole.UNCHANGED: rich_styler("green"),
    StyleRole.WOULD_CHANGE: rich_styler("bold bright_yellow"),
    StyleRole.CHANGED: rich_styler("bold bright_green"),
    # Other common buckets
    StyleRole.SKIPPED: rich_styler("blue"),
    StyleRole.UNSUPPORTED: rich_styler("magenta"),
    StyleRole.BLOCKED_POLICY: rich_styler("red"),
    StyleRole.PENDING: rich_styler("italic grey50"),
    # Unified diffs
    StyleRole.DIFF_HEADER: rich_styler("bold cyan"),
    StyleRole.DIFF_META: rich_styler("italic blue"),
    StyleRole.DIFF_ADD: rich_styler("bold green"),
    StyleRole.DIFF_DEL: rich_styler("bold red"),
    StyleRole.DIFF_LINE_NO: rich_styler("dim white"),
    # Generic formats
    StyleRole.HEADING_TITLE: rich_styler("bold underline"),
    StyleRole.MARKER_LINE: rich_styler("dim cyan"),
    StyleRole.CONFIG_FILE: rich_styler("cyan"),
}


@dataclass(frozen=True, kw_only=True, slots=True)
class Theme:
    """Theme for mapping `StyleRole` values to concrete terminal stylers.

    A theme consists of a required base mapping plus optional per-role overrides.

    Lookups are performed in this order:
        1) overrides (if provided)
        2) base mapping
        3) `no_style_for_role` fallback

    This keeps the default styling stable while allowing caller-controlled theming
    (e.g., alternate palettes, accessibility themes, tests).

    Themes intentionally remain immutable, mapping-based value objects. This keeps
    the semantic styling boundary small, strictly typed, and independent from any
    future user-facing theme configuration format.

    Attributes:
        base: Base mapping from `StyleRole` to a `TextStyler`.
        overrides: Optional role-specific overrides.
    """

    base: Mapping[StyleRole, TextStyler]
    overrides: Mapping[StyleRole, TextStyler] | None = None

    def styler_for(self, role: StyleRole) -> TextStyler:
        """Return the concrete `TextStyler` for a semantic role."""
        if self.overrides is not None and role in self.overrides:
            return self.overrides[role]
        return self.base.get(role, no_style_for_role)


DEFAULT_THEME: Theme = Theme(base=DEFAULT_STYLE_ROLE_MAPPING)


def style_for_role(
    role: StyleRole,
    *,
    styled: bool = True,
    theme: Theme = DEFAULT_THEME,
) -> TextStyler:
    """Return a string styler for the given semantic `StyleRole`.

    This function maps core semantic roles onto concrete terminal styling.
    It is intentionally CLI-only and depends on Rich through this adapter module.

    Callers should still gate styling themselves when color is disabled and
    fall back to a no-op.

    Args:
        role: The semantic style role to map.
        styled: Whether to render styled.
        theme: Theme used to resolve the concrete `TextStyler`.

    Returns:
        A callable that styles a string.
    """
    return theme.styler_for(role) if styled else no_style_for_role


def maybe_style(
    text: str,
    *,
    styler: TextStyler,
    styled: bool,
) -> str:
    """Conditionally apply a styling function.

    This is a tiny helper used by TEXT emitters to avoid scattering `if color:` checks throughout
    rendering code.

    Args:
        text: Input text to render.
        styler: Callable that applies styling to a string.
        styled: When False, return `text` unchanged.

    Returns:
        Styled text when enabled; otherwise the original `text`.
    """
    return styler(text) if styled else text
