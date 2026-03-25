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
(currently backed by yachalk).

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
from yachalk import chalk
from topmark.cli.presentation import Theme, DEFAULT_THEME, style_for_role
from topmark.core.presentation import StyleRole

custom_theme = Theme(
    base=DEFAULT_THEME.base,
    overrides={
        StyleRole.ERROR: chalk.bg_red.white.bold,
        StyleRole.WARNING: chalk.yellow,
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
        StyleRole.CHANGED: chalk.cyan,
    },
)

minimal_theme = Theme(
    base=soft_theme.base,
    overrides={
        StyleRole.ERROR: chalk.red,
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
from typing import TypeAlias

from yachalk import chalk

from topmark.core.presentation import StyleRole

TextStyler: TypeAlias = Callable[[str], str]
"""Callable which styles a str."""


def no_style_for_role(s: str) -> str:
    """Return string verbatim (no-op)."""
    return s


DEFAULT_STYLE_ROLE_MAPPING: dict[StyleRole, TextStyler] = {
    # Severities
    StyleRole.INFO: chalk.blue,
    StyleRole.WARNING: chalk.yellow_bright,
    StyleRole.ERROR: chalk.red_bright.bold,
    # Generic outcomes / states
    StyleRole.OK: chalk.green,
    StyleRole.MUTED: chalk.gray,
    StyleRole.EMPHASIS: chalk.bold,
    # Change semantics
    StyleRole.UNCHANGED: chalk.green,
    StyleRole.WOULD_CHANGE: chalk.yellow_bright.bold,
    StyleRole.CHANGED: chalk.green_bright.bold,
    # Other common buckets
    StyleRole.SKIPPED: chalk.blue,
    StyleRole.UNSUPPORTED: chalk.magenta,
    StyleRole.BLOCKED_POLICY: chalk.red,
    StyleRole.PENDING: chalk.gray.italic,
    # Unified diffs
    StyleRole.DIFF_HEADER: chalk.bold.cyan,
    StyleRole.DIFF_META: chalk.italic.blue,
    StyleRole.DIFF_ADD: chalk.bold.green,
    StyleRole.DIFF_DEL: chalk.bold.red,
    StyleRole.DIFF_LINE_NO: chalk.white.dim,
    # Generic formats
    StyleRole.HEADING_TITLE: chalk.bold.underline,
    StyleRole.MARKER_LINE: chalk.cyan.dim,
    StyleRole.CONFIG_FILE: chalk.cyan,
}


@dataclass(frozen=True, slots=True)
class Theme:
    """Theme for mapping `StyleRole` values to concrete terminal stylers.

    A theme consists of a required base mapping plus optional per-role overrides.

    Lookups are performed in this order:
        1) overrides (if provided)
        2) base mapping
        3) `_noop` fallback

    This keeps the default styling stable while allowing caller-controlled theming
    (e.g., alternate palettes, accessibility themes, tests).

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
    It is intentionally CLI-only (depends on `yachalk`).

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
        styler: Callable that applies styling to a string (for example, a `chalk.*` function).
        styled: When False, return `text` unchanged.

    Returns:
        Styled text when enabled; otherwise the original `text`.
    """
    return styler(text) if styled else text
