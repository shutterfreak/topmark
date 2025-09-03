# topmark:header:start
#
#   file         : cli_types.py
#   file_relpath : src/topmark/cli/cli_types.py
#   project      : TopMark
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

import glob
import logging
from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Iterable,
    NoReturn,
    Protocol,
    TypedDict,
    TypeVar,
    cast,
)

import click

from topmark.rendering.formats import HeaderOutputFormat

if TYPE_CHECKING:
    from click.shell_completion import CompletionItem as ClickCompletionItem

    class ParamTypeBase(Protocol):
        """Typed base to avoid subclassing Any when Click lacks stubs."""

        name: str

else:
    # At runtime, subclass the real Click type
    ParamTypeBase = click.ParamType  # type: ignore[assignment]

# Type variable bounded to Enum for generic EnumParam
E = TypeVar("E", bound=Enum)


class ArgsNamespace(TypedDict, total=False):
    """Namespace for parsed CLI arguments and options in TopMark.

    This TypedDict is used to represent all relevant CLI arguments and options
    passed through TopMark commands and subcommands. It facilitates type-safe
    access and transfer of parsed CLI state, including global options, config
    file overrides, file selection, filtering, and formatting flags.

    Attributes:
        log_level: Verbosity level for logging.
        no_config: Whether to ignore local config files.
        config_files: List of extra config file paths.
        files: List of file paths to process.
        stdin: Whether to read file paths from stdin.
        include_patterns: Glob patterns of files to include.
        include_from: Files containing include patterns.
        exclude_patterns: Glob patterns of files to exclude.
        exclude_from: Files containing exclude patterns.
        file_types: Restrict to given file types.
        relative_to: Root directory for relative paths.
        align_fields: Align header fields with colons.
        header_format: Header output format (file type aware, plain, or json).
    """

    # Global options: retrieve from ctx.obj
    log_level: int

    # TopMark Command
    # command: TopMarkCommand

    # Command options: config
    no_config: bool | None
    config_files: list[str] | None

    # Command arguments
    files: list[str]
    files_from: list[str]

    # Command options: common_file_and_filtering_options
    stdin: bool | None
    include_patterns: list[str] | None
    include_from: list[str] | None
    exclude_patterns: list[str] | None
    exclude_from: list[str] | None
    file_types: list[str] | None
    relative_to: str | None

    # Command options: formatting
    align_fields: bool | None
    header_format: HeaderOutputFormat | None


def build_args_namespace(
    *,
    log_level: int = logging.WARNING,
    # command: TopMarkCommand = TopMarkCommand.NONE,
    no_config: bool | None = None,
    config_files: list[str] | None = None,
    files: list[str] | None = None,
    files_from: list[str] | None = None,
    stdin: bool | None = None,
    include_patterns: list[str] | None = None,
    include_from: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    exclude_from: list[str] | None = None,
    file_types: list[str] | None = None,
    relative_to: str | None = None,
    align_fields: bool | None = None,
    header_format: HeaderOutputFormat | None = None,
) -> ArgsNamespace:
    """Build an ArgsNamespace dictionary for CLI argument passing.

    Args:
        log_level: Verbosity level for logging.
        no_config: Whether to ignore local config files.
        config_files: List of extra config file paths.
        files: List of file paths to process.
        files_from: List of files containing newline-delimited paths.
        stdin: Whether to read file paths from stdin.
        include_patterns: Glob patterns of files to include.
        include_from: Files containing include patterns.
        exclude_patterns: Glob patterns of files to exclude.
        exclude_from: Files containing exclude patterns.
        file_types: Restrict to given file types.
        relative_to: Root directory for relative paths.
        align_fields: Align header fields with colons.
        header_format: Header output format (native, plain, or json).

    Returns:
        Dictionary of CLI argument values for use throughout the CLI.
    """
    return {
        "log_level": log_level,
        # "command": command,
        "no_config": no_config,
        "config_files": config_files,
        "files": files if files is not None else [],
        "files_from": files_from if files_from is not None else [],
        "stdin": stdin,
        "include_patterns": include_patterns,
        "include_from": include_from,
        "exclude_patterns": exclude_patterns,
        "exclude_from": exclude_from,
        "file_types": file_types,
        "relative_to": relative_to,
        "align_fields": align_fields,
        "header_format": header_format,
    }


# --- Custom Click parameter types and validators for TopMark CLI ---


class EnumChoiceParam(ParamTypeBase, Generic[E]):
    """A Click parameter type that converts a string to a member of a given Enum."""

    # Add instance variable annotations for maximum clarity
    enum_cls: type[E]
    name: str
    choices: list[str]

    def __init__(self, enum_cls: type[E]):
        """Initialize the EnumParam instance."""
        self.enum_cls = enum_cls
        self.name = self.enum_cls.__name__.lower()
        # Assume the enum exposes string-valued members (e.g., HeaderOutputFormat)
        self.choices = [cast("str", getattr(e, "value", str(e))) for e in self.enum_cls]

    def _fail_noreturn(
        self,
        message: str,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> NoReturn:
        """Raise a BadParameter with a NoReturn signature (clear to type checkers)."""
        raise click.BadParameter(message, param=param, ctx=ctx)

    def convert(
        self,
        value: str | None,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> E | None:
        """Converts a string to a member of the Enum."""
        if value is None:
            return None

        # Case-insensitive lookup by the enum's string value
        lookup: dict[str, E] = {
            cast("str", getattr(choice, "value", str(choice))).lower(): choice
            for choice in cast("Iterable[E]", self.enum_cls)
        }

        key = value.lower()
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
        ctx: click.Context,  # pylint: disable=unused-argument
        param: click.Parameter,  # pylint: disable=unused-argument
        incomplete: str,
    ) -> list["ClickCompletionItem"]:
        """Tab completion for Click.

        Bash: `eval "$(_TOPMARK_COMPLETE=bash_source topmark)"`
        Zsh: `eval "$(_TOPMARK_COMPLETE=zsh_source topmark)"`
        """
        # Runtime import to avoid import-time dependency for non-completion paths
        from click.shell_completion import (
            CompletionItem as RuntimeCompletionItem,
        )  # Click 8.x

        prefix = (incomplete or "").lower()
        items: list["ClickCompletionItem"] = []
        for e in cast("Iterable[E]", self.enum_cls):
            val = str(getattr(e, "value", e))
            if val.lower().startswith(prefix):
                items.append(RuntimeCompletionItem(val))
        return items

    def __repr__(self) -> str:
        """Return a string representation."""
        return f"EnumParam({self.enum_cls.__name__})"


def FileTypeParam(
    ctx: click.Context,  # pylint: disable=unused-argument
    param: click.Parameter,  # pylint: disable=unused-argument
    value: Any,
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
    if value is None:
        return None
    path = Path(value)
    # Check if the path exists and is a file.
    if not path.exists() or not path.is_file():
        raise click.BadParameter(f"File not found or not a file: {value}")
    return path


def GlobParam(
    ctx: click.Context,  # pylint: disable=unused-argument
    param: click.Parameter,  # pylint: disable=unused-argument
    value: Any,
) -> list[Path]:
    """Validator: Expand a glob pattern CLI argument to a list of file paths.

    Expands the given glob pattern string into a list of Path objects matching the pattern.

    Args:
        ctx: Click context.
        param: The Click parameter.
        value: The glob pattern string.

    Returns:
        List of Path objects matching the glob pattern, or an empty list if value is None.
    """
    if value is None:
        return []
    # Use glob.glob for shell-style wildcards; return as Path objects.
    return [Path(p) for p in glob.glob(value, recursive=True)]
