# topmark:header:start
#
#   file         : options.py
#   file_relpath : src/topmark/cli/options.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Common CLI options and helpers for TopMark.

This module defines reusable Click option decorators and helper functions
used throughout the TopMark CLI commands.

Additional utilities:

- ``underscored_trap_option``: registers hidden underscored spellings like
  ``--exclude_from`` that raise a friendly "Did you mean --exclude-from?" error.
"""

from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar, cast

import click
from click.core import ParameterSource

from topmark.rendering.formats import HeaderOutputFormat

from .cli_types import EnumParam

# Custom decorators

# Define a ParamSpec to capture the parameters of the decorated function
P = ParamSpec("P")
# Define a TypeVar for the return type of the decorated function
R = TypeVar("R")


def typed_command_of(
    g: Any, *args: Any, **kwargs: Any
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Return a typed decorator that registers a command on a specific group."""

    def decorator(f: Callable[P, R]) -> Callable[P, R]:
        return cast(Callable[P, R], g.command(*args, **kwargs)(f))

    return decorator


def typed_group(*args: Any, **kwargs: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Typed wrapper around click.group to keep function types."""
    # def decorator(f: Callable[P, R]) -> Callable[P, R]:
    #     return cast(Callable[P, R], click.group(*args, **kwargs)(f))

    # return decorator
    return cast(Callable[[Callable[P, R]], Callable[P, R]], click.group(*args, **kwargs))


def typed_option(*args: Any, **kwargs: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Typed wrapper around click.option to keep function types."""
    return cast(Callable[[Callable[P, R]], Callable[P, R]], click.option(*args, **kwargs))


def trap_underscored_option(ctx: click.Context, param: click.Option, _value: object) -> None:
    """Raise a helpful error for underscored long options (e.g., --exclude_from).

    Runs during option parsing (is_eager=True) so we can show a friendly hint
    instead of the generic "No such option" error.
    """
    # Only trigger if the user actually typed the option
    name = getattr(param, "name", None)
    try:
        src = ctx.get_parameter_source(name) if name else None
    except Exception:
        src = None
    if src is not ParameterSource.COMMANDLINE:
        return

    bad = param.opts[0] if param.opts else "--?"
    suggestion = bad.replace("_", "-")
    raise click.UsageError(f"Unknown option: {bad}. Did you mean {suggestion}?")


def underscored_trap_option(*names: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Register hidden underscored spellings that raise a helpful error.

    This wraps :func:`click.option` with common settings for underscored
    long-option traps, so callers don't repeat the same boilerplate.

    It also assigns a **unique destination name** for the hidden option so
    Click's parameter source tracking does not overlap with the real option's
    destination (e.g., ``exclude_from``). Without this, the trap callback can
    incorrectly detect COMMANDLINE source when the *hyphenated* option was
    used, leading to false positives.

    Args:
        *names: One or more underscored long option names to trap,
            e.g. "--exclude_from". Multiple names are supported so a
            single decorator can catch several spellings.

    Returns:
        A decorator compatible with Click's option stacking.
    """
    if not names:
        raise ValueError("underscored_trap_option requires at least one option name")

    first = names[0]
    # Create a unique, non-conflicting Python destination name for the hidden option
    dest = f"_trap_{first.lstrip('-').replace('-', '_')}"

    return typed_option(
        *names,
        dest,
        hidden=True,
        expose_value=False,
        is_eager=True,
        multiple=True,
        callback=trap_underscored_option,
    )


def typed_argument(*args: Any, **kwargs: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Typed wrapper around click.argument to keep function types."""
    # def decorator(f: Callable[P, R]) -> Callable[P, R]:
    #     return click.argument(*args, **kwargs)(f)

    # return decorator
    return cast(Callable[[Callable[P, R]], Callable[P, R]], click.argument(*args, **kwargs))


def common_logging_options(f: Callable[P, R]) -> Callable[P, R]:
    """Apply common logging options to a Click command.

    Adds ``-v/--verbose`` and ``-q/--quiet`` options.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = click.option(
        "--verbose",
        "-v",
        type=int,
        count=True,
        help="Increase log verbosity (can be repeated)",
    )(f)
    f = click.option(
        "-q",
        "--quiet",
        type=int,
        count=True,
        help="Decrease log verbosity (can be repeated)",
    )(f)

    return f


def common_config_options(f: Callable[P, R]) -> Callable[P, R]:
    """Apply common configuration options to a Click command.

    Adds ``--no-config`` and ``--config/-c`` options.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = click.option(
        "--no-config",
        "no_config",
        is_flag=True,
        help="Ignore local project config files (only use defaults).",
    )(f)
    f = underscored_trap_option("--no_config")(f)
    f = click.option(
        "--config",
        "config_paths",
        multiple=True,
        metavar="FILE",
        type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
        help="Additional config file(s) to load and merge.",
    )(f)

    return f


def common_file_and_filtering_options(f: Callable[P, R]) -> Callable[P, R]:
    """Apply common file selection and filtering options.

    Adds options such as ``--stdin``, ``--include``, ``--exclude``, ``--file-type``,
    and ``--relative-to``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = click.option(
        "--stdin",
        is_flag=True,
        help="Read input paths from stdin instead of arguments.",
    )(f)
    f = click.option(
        "--include",
        "-i",
        "include_patterns",
        multiple=True,
        help="Glob patterns of files to include.",
    )(f)
    f = click.option(
        "--include-from",
        multiple=True,
        help="Read include patterns from file(s).",
    )(f)
    f = underscored_trap_option("--include_from")(f)
    f = click.option(
        "--exclude",
        "-e",
        "exclude_patterns",
        multiple=True,
        help="Glob patterns of files to exclude.",
    )(f)
    f = click.option(
        "--exclude-from",
        multiple=True,
        help="Read exclude patterns from file(s).",
    )(f)
    f = underscored_trap_option("--exclude_from")(f)
    f = click.option(
        "--file-type",
        "file_types",
        multiple=True,
        help="Restrict to given file types.",
    )(f)
    f = underscored_trap_option("--file_type")(f)
    f = click.option(
        "--relative-to",
        help="Specify the root from which relative paths are computed.",
    )(f)
    f = underscored_trap_option("--relative_to")(f)

    return f


def common_header_formatting_options(f: Callable[P, R]) -> Callable[P, R]:
    """Apply common header formatting options.

    Adds ``--align-fields/--no-align-fields`` and ``--header-format``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = click.option(
        "--align-fields/--no-align-fields",
        is_flag=True,
        help="Align header fields with colons.",
    )(f)
    f = underscored_trap_option("--align_fields")(f)
    f = underscored_trap_option("--no_align_fields")(f)
    f = click.option(
        "--header-format",
        "header_format",
        type=EnumParam(HeaderOutputFormat),
        help=f"Select the header format ({', '.join(e.value for e in HeaderOutputFormat)}).",
    )(f)
    f = underscored_trap_option("--header_format")(f)

    return f
