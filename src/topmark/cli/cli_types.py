# topmark:header:start
#
#   project      : TopMark
#   file         : cli_types.py
#   file_relpath : src/topmark/cli/cli_types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared Click parameter types and argument parsing helpers for TopMark.

This module contains reusable Click parameter validators and custom parameter
classes used by TopMark CLI commands. The helpers stay focused on CLI argument
conversion and validation; command-level input planning lives in
`topmark.cli.io`.
"""

from __future__ import annotations

import glob
import re
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final
from typing import Generic
from typing import TypeVar

import click

from topmark.registry.query import RegistryIdentityQuery
from topmark.registry.query import RegistryRegex

if TYPE_CHECKING:
    from click.shell_completion import CompletionItem as ClickCompletionItem

# Type variable bounded to Enum for generic enum choice parameters.
E = TypeVar(name="E", bound=StrEnum)


REGISTRY_QUERY_METAVAR: Final[str] = "QUERY"
"""Metavariable used for positional registry identity queries."""

REGISTRY_REGEX_METAVAR: Final[str] = "PATTERN"
"""Metavariable used for registry regular-expression filters."""


# --- Custom Click parameter types and validators for TopMark CLI ---


class CliWriteMode(StrEnum):
    """Private CLI vocabulary for selecting the write destination and strategy.

    Runtime code decomposes this Click-boundary type into the existing
    [`OutputTarget`][topmark.config.types.OutputTarget] and
    [`FileWriteStrategy`][topmark.config.types.FileWriteStrategy] model types.
    """

    ATOMIC = "atomic"
    INPLACE = "inplace"
    STDOUT = "stdout"


class RegistryQueryParam(click.ParamType[RegistryIdentityQuery]):
    """Parse one positional registry identity query."""

    name: str = REGISTRY_QUERY_METAVAR

    def convert(
        self,
        value: str | RegistryIdentityQuery | None,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> RegistryIdentityQuery:
        """Convert one CLI positional query to a typed identity query.

        Args:
            value: Raw query text supplied by Click.
            param: Click parameter being converted.
            ctx: Active Click context.

        Returns:
            A typed registry identity query.

        Note:
            Raises `click.BadParameter` if the query is missing or cannot be parsed as a
            valid `RegistryIdentityQuery`.
        """
        if value is None:
            self.fail(
                "Registry query not set",
                param=param,
                ctx=ctx,
            )

        if isinstance(value, RegistryIdentityQuery):
            return value

        try:
            return RegistryIdentityQuery.parse(value)
        except ValueError as error:
            self.fail(
                f"Invalid registry query: {error}",
                param=param,
                ctx=ctx,
            )


class RegistryRegexParam(click.ParamType[RegistryRegex]):
    """Parse one regular expression used to select a qualified registry key."""

    name: str = REGISTRY_REGEX_METAVAR

    def convert(
        self,
        value: str | RegistryRegex | None,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> RegistryRegex:
        """Convert one CLI regular expression to a typed selector.

        Args:
            value: Raw regex text supplied by Click.
            param: Click parameter being converted.
            ctx: Active Click context.

        Returns:
            A typed registry regex expression.

        Note:
            Raises `click.BadParameter` if the regex is missing or cannot be parsed as a
            valid `RegistryRegex`.
        """
        if value is None:
            self.fail(
                "Regular expression not set",
                param=param,
                ctx=ctx,
            )

        if isinstance(value, RegistryRegex):
            return value

        try:
            return RegistryRegex.parse(value)
        except re.error as error:
            self.fail(
                f"Invalid regular expression: {error}",
                param=param,
                ctx=ctx,
            )


class EnumChoiceParam(click.ParamType[E | None], Generic[E]):
    """Click parameter type that converts CLI text to an enum member.

    The parameter requires case-sensitive input by default, can optionally
    accept case-insensitive input, and can present and require kebab-case
    spellings for string-valued enum members whose internal values use
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
        case_sensitive: bool = True,
        kebab_case: bool = False,
    ) -> None:
        self.enum_cls = enum_cls
        self.name = self.enum_cls.__name__.lower()
        self.case_sensitive = case_sensitive
        self.kebab_case = kebab_case
        # `choices` contains the user-facing spellings shown in help/errors.
        # StrEnum values are expected to be string-like for TopMark CLI options.
        self.choices = self.choices = [self._display_value(e.value) for e in self.enum_cls]

    def _display_value(self, raw: str) -> str:
        """Return the user-facing spelling for an enum value."""
        display: str = raw.replace("_", "-") if self.kebab_case else raw
        return display

    def _normalize_input(self, raw: str) -> str:
        """Normalize CLI input for case-sensitive or case-insensitive lookup.

        Delimiter spelling is deliberately preserved so kebab-case display
        choices remain the only accepted CLI spellings. When `case_sensitive`
        is disabled, the input is lower-cased.
        """
        return raw if self.case_sensitive else raw.lower()

    def convert(
        self,
        value: str | E | None,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> E | None:
        """Convert CLI text to a member of the configured enum.

        Args:
            value: Raw parameter text value supplied by Click.
            param: Click parameter being converted.
            ctx: Active Click context.

        Returns:
            A typed Enum member.

        Note:
            Raises `click.BadParameter` if the parameter value cannot be parsed
            as a valid `EnumChoiceParam`.
        """
        if value is None:
            return None

        if isinstance(value, self.enum_cls):
            return value

        # Now value is str | StrEnum:
        raw_input: str = value.value if isinstance(value, StrEnum) else value

        lookup: dict[str, tuple[str, E]] = {}
        for choice in self.enum_cls:
            raw_value: str = str(choice.value)
            display_value: str = self._display_value(raw_value)
            lookup[self._normalize_input(display_value)] = (display_value, choice)

        key: str = self._normalize_input(raw_input)
        if key in lookup:
            return lookup[key][1]

        suggestion: str | None = None
        suggested_input: str = raw_input.lower()
        if self.kebab_case:
            suggested_input = suggested_input.replace("_", "-")
        suggested_match: tuple[str, E] | None = lookup.get(self._normalize_input(suggested_input))
        if suggested_input != raw_input and suggested_match is not None:
            suggestion = suggested_match[0]

        # Raise a BadParameter exception for invalid input.
        suggestion_text: str = f" Did you mean '{suggestion}'?" if suggestion else ""
        choices_text: str = ", ".join(self.choices)
        self.fail(
            f"Invalid value '{raw_input}'.{suggestion_text} Must be one of: {choices_text}",
            param=param,
            ctx=ctx,
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

        # Runtime import to avoid import-time dependency for non-completion paths.
        from click.shell_completion import CompletionItem as RuntimeCompletionItem  # Click 8.x

        prefix: str = self._normalize_input(incomplete or "")
        items: list[ClickCompletionItem] = []
        for e in self.enum_cls:
            # e is a StrEnum
            display_value: str = self._display_value(e.value)
            normalized_value: str = self._normalize_input(display_value)
            if normalized_value.startswith(prefix):
                items.append(RuntimeCompletionItem(display_value))
        return items

    def __repr__(self) -> str:
        """Return a debugging representation for this parameter type."""
        return f"EnumChoiceParam({self.enum_cls.__name__})"


def FileTypeParam(
    ctx: click.Context,
    param: click.Parameter,
    value: object,
) -> Path | None:
    """Validate and convert a CLI argument to an existing file path.

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
        raise click.BadParameter(
            f"File not found or not a file: {value}",
            ctx=ctx,
            param=param,
        )
    return path


def GlobParam(
    ctx: click.Context,
    param: click.Parameter,
    value: object,
) -> list[Path]:
    """Expand a glob pattern CLI argument to matching file paths.

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
