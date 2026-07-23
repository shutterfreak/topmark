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
        """Minimal typed Click parameter base used only during type checking.

        Runtime code subclasses `click.ParamType` directly. This protocol keeps
        `EnumChoiceParam` from inheriting from `Any` when Click stubs are not
        precise enough for strict type checking.
        """

        name: str
else:
    # At runtime, subclass the real Click type.
    ParamTypeBase = click.ParamType  # type: ignore[assignment]

# Type variable bounded to Enum for generic enum choice parameters.
E = TypeVar("E", bound=Enum)


# --- Custom Click parameter types and validators for TopMark CLI ---


class CliWriteMode(str, Enum):
    """Private CLI vocabulary for selecting the write destination and strategy.

    Runtime code decomposes this Click-boundary type into the existing
    [`OutputTarget`][topmark.config.types.OutputTarget] and
    [`FileWriteStrategy`][topmark.config.types.FileWriteStrategy] model types.
    """

    ATOMIC = "atomic"
    INPLACE = "inplace"
    STDOUT = "stdout"


class EnumChoiceParam(ParamTypeBase, Generic[E]):
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
        # Enum values are expected to be string-like for TopMark CLI options.
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
        """Convert CLI text to a member of the configured enum."""
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return value
        raw_input: str = cast("str", value)

        lookup: dict[str, tuple[str, E]] = {}
        for choice in cast("Iterable[E]", self.enum_cls):
            raw_value: str = cast("str", getattr(choice, "value", str(choice)))
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
        self._fail_noreturn(
            f"Invalid value '{raw_input}'.{suggestion_text} Must be one of: {choices_text}",
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

        # Runtime import to avoid import-time dependency for non-completion paths.
        from click.shell_completion import CompletionItem as RuntimeCompletionItem  # Click 8.x

        prefix: str = self._normalize_input(incomplete or "")
        items: list[ClickCompletionItem] = []
        for e in cast("Iterable[E]", self.enum_cls):
            raw_value: str = cast("str", getattr(e, "value", str(e)))
            display_value: str = self._display_value(raw_value)
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
        raise click.BadParameter(f"File not found or not a file: {value}")
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
