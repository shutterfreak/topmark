# topmark:header:start
#
#   project      : TopMark
#   file         : cli_types.py
#   file_relpath : src/topmark/cli/cli_types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared CLI parameter types and argument parsing helpers for TopMark.

This module serves as the central container for shared CLI argument types, validators,
and helpers in TopMark. It defines the ArgsNamespace TypedDict for consistent
argument passing throughout the CLI, as well as reusable validator functions and
custom Click parameter types for argument parsing (such as file paths and globs).
These utilities ensure robust and uniform handling of CLI parameters
across all TopMark commands and subcommands.
"""

from __future__ import annotations

import glob
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Generic
from typing import NoReturn
from typing import Protocol
from typing import TypeVar
from typing import cast

import click

if TYPE_CHECKING:
    from collections.abc import Iterable

    from click.shell_completion import CompletionItem as ClickCompletionItem

    class ParamTypeBase(Protocol):
        """Typed base to avoid subclassing Any when Click lacks stubs."""

        name: str

else:
    # At runtime, subclass the real Click type
    ParamTypeBase = click.ParamType  # type: ignore[assignment]

# Type variable bounded to Enum for generic EnumParam
E = TypeVar("E", bound=Enum)


# --- Custom Click parameter types and validators for TopMark CLI ---


class EnumChoiceParam(ParamTypeBase, Generic[E]):
    """A Click parameter type that converts a string to a member of a given Enum.

    The parameter can optionally accept case-insensitive input and present/accept
    kebab-case spellings for string-valued enum members whose internal values use
    underscores.
    """

    # Add instance variable annotations for maximum clarity
    enum_cls: type[E]
    name: str
    choices: list[str]
    case_sensitive: bool
    kebab_case: bool

    def __init__(
        self,
        enum_cls: type[E],
        *,
        case_sensitive: bool = False,
        kebab_case: bool = False,
    ) -> None:
        self.enum_cls = enum_cls
        self.name = self.enum_cls.__name__.lower()
        self.case_sensitive = case_sensitive
        self.kebab_case = kebab_case
        # Assume the enum exposes string-valued members (e.g., OutputFormat).
        # `choices` contains the user-facing spellings shown in help/errors.
        self.choices = [
            self._display_value(cast("str", getattr(e, "value", str(e)))) for e in self.enum_cls
        ]

    def _fail_noreturn(
        self,
        message: str,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> NoReturn:
        """Raise a BadParameter with a NoReturn signature (clear to type checkers)."""
        raise click.BadParameter(message, param=param, ctx=ctx)

    def _display_value(self, raw: str) -> str:
        """Return the user-facing spelling for an enum value."""
        display: str = raw.replace("_", "-") if self.kebab_case else raw
        return display

    def _normalize_input(self, raw: str) -> str:
        """Normalize CLI input for lookup against enum member values.

        When `kebab_case` is enabled, both kebab-case and snake_case inputs are
        accepted by normalizing `-` to `_`. When `case_sensitive` is disabled,
        the normalized input is lower-cased.
        """
        normalized: str = raw.replace("-", "_") if self.kebab_case else raw
        return normalized if self.case_sensitive else normalized.lower()

    def convert(
        self,
        value: str | None,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> E | None:
        """Converts a string to a member of the Enum."""
        if value is None:
            return None

        lookup: dict[str, E] = {
            self._normalize_input(cast("str", getattr(choice, "value", str(choice)))): choice
            for choice in cast("Iterable[E]", self.enum_cls)
        }

        key: str = self._normalize_input(value)
        if key in lookup:
            return lookup[key]

        # Raise a BadParameter exception for invalid input
        self._fail_noreturn(
            f"Invalid value '{value}'. Must be one of: {', '.join(self.choices)}",
            param,
            ctx,
        )

    def shell_complete(
        self,
        ctx: click.Context,
        param: click.Parameter,
        incomplete: str,
    ) -> list[ClickCompletionItem]:
        """Tab completion for Click.

        Bash: `eval "$(_TOPMARK_COMPLETE=bash_source topmark)"`
        Zsh: `eval "$(_TOPMARK_COMPLETE=zsh_source topmark)"`
        """
        _, _ = ctx, param

        # Runtime import to avoid import-time dependency for non-completion paths
        from click.shell_completion import CompletionItem as RuntimeCompletionItem  # Click 8.x

        prefix: str = self._normalize_input(incomplete or "")
        items: list[ClickCompletionItem] = []
        for e in cast("Iterable[E]", self.enum_cls):
            raw_value: str = cast("str", getattr(e, "value", str(e)))
            display_value: str = self._display_value(raw_value)
            normalized_value: str = self._normalize_input(raw_value)
            if normalized_value.startswith(prefix):
                items.append(RuntimeCompletionItem(display_value))
        return items

    def __repr__(self) -> str:
        """Return a string representation."""
        return f"EnumChoiceParam({self.enum_cls.__name__})"


def FileTypeParam(
    ctx: click.Context,
    param: click.Parameter,
    value: object,
) -> Path | None:
    """Validator: Ensure a CLI argument is a valid file path.

    Validates and converts the CLI argument to a Path, raising an error if it does not exist
    or is not a file.

    Args:
        ctx: Click context.
        param: The Click parameter.
        value: The CLI argument value to validate.

    Returns:
        The validated file path, or None if value is None.

    Raises:
        click.BadParameter: If the file does not exist or is not a file.
    """
    _, _ = ctx, param

    if value is None:
        return None
    path: Path = Path(str(value))
    # Check if the path exists and is a file.
    if not path.exists() or not path.is_file():
        raise click.BadParameter(f"File not found or not a file: {value}")
    return path


def GlobParam(
    ctx: click.Context,
    param: click.Parameter,
    value: object,
) -> list[Path]:
    """Validator: Expand a glob pattern CLI argument to a list of file paths.

    Expands the given glob pattern string into a list of `Path` objects matching the
    pattern.

    - Relative patterns are expanded via `Path.glob()`.
    - Absolute patterns are expanded via `glob.glob(..., recursive=True)` because
      `Path.glob()` does not support absolute patterns.

    Both approaches support `**` for recursive matches.

    Args:
        ctx: Click context.
        param: The Click parameter.
        value: The glob pattern string.

    Returns:
        Paths matching the glob pattern, or an empty list if `value` is None.
    """
    _, _ = ctx, param

    if value is None:
        return []

    pattern: str = str(value)

    # Re-enable support for absolute glob patterns.
    # `Path.glob()` does not support absolute patterns, so we use stdlib `glob.glob()`
    # for those while keeping `Path.glob()` for relative patterns.
    if Path(pattern).is_absolute():
        # Note: `glob.glob` supports `**` when `recursive=True`.
        return [Path(p) for p in glob.glob(pattern, recursive=True)]  # noqa: PTH207

    # Relative patterns: use Path.glob (supports `**` for recursive patterns).
    return list(Path().glob(pattern))
