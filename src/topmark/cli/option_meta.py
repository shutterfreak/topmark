# topmark:header:start
#
#   project      : TopMark
#   file         : option_meta.py
#   file_relpath : src/topmark/cli/option_meta.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI option metadata helpers.

This module contains small, parser-adjacent metadata used by TopMark-owned
validation and diagnostic rendering. Click option declarations remain in
`topmark.cli.options`; this module must not become a second parser model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from topmark.cli.keys import CliOpt
from topmark.cli.keys import CliShortOpt


@dataclass(frozen=True, slots=True)
class CliOptionMeta:
    """Human-facing metadata for one CLI option spelling.

    Attributes:
        long: Canonical long option spelling.
        short: Optional short alias spelling.
        hidden_aliases: Compatibility aliases accepted by Click but hidden from help.
    """

    long: str
    short: str | None = None
    hidden_aliases: tuple[str, ...] = ()

    def label(self) -> str:
        """Return the option label used in human-facing diagnostics.

        Returns:
            The canonical long spelling, followed by the short alias when available.
        """
        if self.short is None:
            return self.long
        return f"{self.long} ({self.short})"


CLI_OPTION_META_BY_LONG: Final[dict[str, CliOptionMeta]] = {
    CliOpt.INCLUDE_FILE_TYPES: CliOptionMeta(
        long=CliOpt.INCLUDE_FILE_TYPES,
        short=CliShortOpt.INCLUDE_FILE_TYPES,
        hidden_aliases=(CliOpt.INCLUDE_FILE_TYPE,),
    ),
    CliOpt.EXCLUDE_FILE_TYPES: CliOptionMeta(
        long=CliOpt.EXCLUDE_FILE_TYPES,
        short=CliShortOpt.EXCLUDE_FILE_TYPES,
        hidden_aliases=(CliOpt.EXCLUDE_FILE_TYPE,),
    ),
    CliOpt.VERBOSE: CliOptionMeta(
        long=CliOpt.VERBOSE,
        short=CliShortOpt.VERBOSE,
    ),
    CliOpt.QUIET: CliOptionMeta(
        long=CliOpt.QUIET,
        short=CliShortOpt.QUIET,
    ),
}
"""Known CLI option metadata keyed by canonical long spelling."""


CLI_HIDDEN_ALIAS_TARGETS: Final[dict[str, str]] = {
    alias: meta.long for meta in CLI_OPTION_META_BY_LONG.values() for alias in meta.hidden_aliases
}
"""Hidden compatibility aliases keyed by alias spelling."""


def format_option_label(option: str) -> str:
    """Return a user-facing option label, including a short alias when known.

    Args:
        option: Option spelling to render. Hidden aliases are resolved to their
            canonical long spelling before rendering.

    Returns:
        Human-facing option label for diagnostics.
    """
    canonical: str = CLI_HIDDEN_ALIAS_TARGETS.get(option, option)
    meta: CliOptionMeta | None = CLI_OPTION_META_BY_LONG.get(canonical)
    if meta is None:
        return canonical
    return meta.label()


def format_option_labels(options: list[str]) -> list[str]:
    """Return user-facing option labels for a list of option spellings.

    Args:
        options: Option spellings to render.

    Returns:
        Rendered labels in the same order as the provided option spellings.
    """
    return [format_option_label(option) for option in options]
