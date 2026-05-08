# topmark:header:start
#
#   project      : TopMark
#   file         : synthetic.py
#   file_relpath : src/topmark/config/resolution/synthetic.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Synthetic configuration provenance markers.

This module defines lightweight typed provenance objects used when TopMark
resolves configuration originating from bundled, generated, or otherwise
non-filesystem TOML sources. These markers allow resolution and merge layers
to distinguish synthetic config origins from real filesystem `Path` values
without relying on fragile string conventions.

Synthetic provenance values are preserved throughout config resolution and are
rendered only at presentation or serialization boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class SyntheticConfigSource:
    """Typed provenance marker for non-filesystem configuration sources.

    TopMark sometimes builds configuration from bundled or generated TOML inputs,
    such as the built-in defaults table or the bundled starter template. These
    sources are not real files and must not be normalized with `Path.resolve()`.

    Use this value object anywhere config provenance needs to distinguish a real
    filesystem `Path` from a synthetic source identifier. Rendering layers may
    convert the marker to `label`, but resolution and merge code should preserve
    the typed value.

    Attributes:
        label: Stable user-facing label used when rendering this synthetic source
            in diagnostics, config dumps, or machine-readable output.
    """

    label: str

    def __str__(self) -> str:
        """Return the stable user-facing source label.

        Returns:
            Synthetic source label suitable for diagnostics and rendered output.
        """
        return self.label


DEFAULT_CONFIG_SOURCE: Final[SyntheticConfigSource] = SyntheticConfigSource("<defaults>")
"""Synthetic provenance marker for the built-in base config layer."""

BUILTIN_DEFAULTS_TOML_SOURCE: Final[SyntheticConfigSource] = SyntheticConfigSource(
    "<built-in topmark defaults>"
)
"""Synthetic provenance marker for the canonical built-in default TOML table."""

BUNDLED_TEMPLATE_TOML_SOURCE: Final[SyntheticConfigSource] = SyntheticConfigSource(
    "<bundled topmark-template.toml>"
)
"""Synthetic provenance marker for the bundled starter TOML template."""
