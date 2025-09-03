# topmark:header:start
#
#   file         : options.py
#   file_relpath : src/topmark/cli/options.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Common CLI option utilities for the Click-based TopMark prototype.

This module centralizes reusable options (verbosity, color) and their
resolution logic, so commands and groups can stay thin. The helpers here are
Click-aware.
"""

import logging
import os
import sys
from enum import Enum
from typing import Callable, Iterable, ParamSpec, TypeVar

import click
from click.core import ParameterSource

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.errors import TopmarkUsageError
from topmark.config.logging import get_logger
from topmark.rendering.formats import HeaderOutputFormat

P = ParamSpec("P")
R = TypeVar("R")

# Custom verbosity levels, mapped to standard logging levels
LOG_LEVELS = {
    "TRACE": 5,  # Custom TRACE (5) sits below logging.DEBUG.
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

logger = get_logger(__name__)


def resolve_verbosity(verbose_count: int, quiet_count: int) -> int:
    """Resolve the final logging level based on verbose and quiet counts.

    Args:
        verbose_count: Number of times the verbose flag (-v) is passed.
        quiet_count: Number of times the quiet flag (-q) is passed.

    Returns:
        The logging level as an integer.

    Raises:
        UsageError: If both verbose and quiet flags are used simultaneously.

    Behavior:
        The --verbose and --quiet options are mutually exclusive.
        Three or more -v flags set TRACE level.
        Two -v flags set DEBUG level.
        One -v flag sets INFO level.
        One or more -q flags set ERROR level.
        Default level is WARNING.
    """
    # They are mutually exclusive
    if verbose_count > 0 and quiet_count > 0:
        raise TopmarkUsageError("The '--verbose' and '--quiet' options are mutually exclusive.")

    # Resolve verbosity levels
    if verbose_count >= 3:  # -vvv
        return LOG_LEVELS["TRACE"]
    if verbose_count == 2:  # -vv
        return LOG_LEVELS["DEBUG"]
    if verbose_count == 1:  # -v
        return LOG_LEVELS["INFO"]

    # Resolve quiet levels
    if quiet_count >= 1:  # -q
        return LOG_LEVELS["ERROR"]
    # Never mute LOG_LEVELS["CRITICAL"]

    # Default is WARNING
    return LOG_LEVELS["WARNING"]


#: Click context settings to allow Black-style extra args and unknown options.
CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "ignore_unknown_options": True,
    "allow_extra_args": True,
}


def common_verbose_options(f: Callable[P, R]) -> Callable[P, R]:
    """Adds --verbose and --quiet options to a command.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function with verbosity options added.

    Behavior:
        Adds -v/--verbose and -q/--quiet options that count occurrences.
        These options are mutually exclusive and control logging verbosity.
    """
    f = click.option(
        "-v",
        "--verbose",
        count=True,
        help="Increase verbosity. Specify up to twice for more detail.",
    )(f)
    f = click.option(
        "-q",
        "--quiet",
        count=True,
        help="Suppress output. Specify up to twice for even less.",
    )(f)
    return f


def common_file_and_filtering_options(f: Callable[P, R]) -> Callable[P, R]:
    """Apply common file selection and filtering options.

    Adds options such as ``--files-from``, ``--include``, ``--exclude``, ``--file-type``,
    and ``--relative-to``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    # Option for STDIN content mode (inserted before --files-from)
    f = click.option(
        "--stdin-filename",
        "stdin_filename",
        type=str,
        default=None,
        help=(
            "Assumed filename when reading a single file's content from STDIN via '-' (dash). "
            "Required when '-' is provided as a PATH."
        ),
    )(f)
    # Option for reading candidate file paths from files
    f = click.option(
        "--files-from",
        "files_from",
        type=str,  # Ensure '-' passes through untouched
        multiple=True,
        help=(
            "Add candidate files by reading newline-delimited paths from file(s) "
            "(use '-' for STDIN)."
            "These paths are added to positional PATHS/globs before filtering. "
        ),
    )(f)
    f = underscored_trap_option("--files_from")(f)
    f = click.option(
        "--include",
        "-i",
        "include_patterns",
        multiple=True,
        help="Filter: keep only files matching these glob patterns (intersection).",
    )(f)
    f = click.option(
        "--include-from",
        type=str,  # Ensure '-' passes through untouched
        multiple=True,
        help="Filter: read include glob patterns from file(s) (use '-' for STDIN).",
    )(f)
    f = underscored_trap_option("--include_from")(f)
    f = click.option(
        "--exclude",
        "-e",
        "exclude_patterns",
        multiple=True,
        help="Filter: remove files matching these glob patterns (subtraction).",
    )(f)
    f = click.option(
        "--exclude-from",
        type=str,  # Ensure '-' passes through untouched
        multiple=True,
        help="Filter: read exclude glob patterns from file(s) (use '-' for STDIN).",
    )(f)
    f = underscored_trap_option("--exclude_from")(f)
    f = click.option(
        "--file-type",
        "file_types",
        multiple=True,
        help="Filter: restrict to given file types (after include/exclude).",
    )(f)
    f = underscored_trap_option("--file_type")(f)
    # TODO: consider adding --extension filter, add a force-handle-file-as-XXX option
    f = click.option(
        "--relative-to",
        help="Reporting: compute relative paths from this directory.",
    )(f)
    f = underscored_trap_option("--relative_to")(f)

    return f


class StdinUse(str, Enum):
    """Identifies which option (if any) should consume STDIN.

    NONE: default; no “...-from” option consumes STDIN.
    FILES_FROM: `--files-from -` wants STDIN (newline-delimited file *paths*).
    INCLUDE_FROM: `--include-from -` wants STDIN (newline-delimited *glob patterns*).
    EXCLUDE_FROM: `--exclude-from -` wants STDIN (newline-delimited *glob patterns*).
    """

    NONE = "none"  # default: positional + --files-from (+ include/exclude filters)
    FILES_FROM = "files-from"  # a single virtual file: '-' + --stdin-filename
    INCLUDE_FROM = "include-from"
    EXCLUDE_FROM = "exclude-from"


def extract_stdin_for_from_options(
    files_from: Iterable[str],
    include_from: Iterable[str],
    exclude_from: Iterable[str],
    stdin_text: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Return (files_from_stdin, include_from_stdin, exclude_from_stdin) texts.

    If one of the options is set to '-', this function returns the raw text
    read from STDIN for that option. If multiple “...-from” options request
    STDIN simultaneously, a UsageError is raised.

    Args:
        files_from: Values passed via ``--files-from`` (may include '-').
        include_from: Values passed via ``--include-from`` (may include '-').
        exclude_from: Values passed via ``--exclude-from`` (may include '-').
        stdin_text: Optional pre-read STDIN content. If provided, it is used
            instead of calling ``click.get_text_stream('stdin').read()``.

    Returns:
        A triple of raw texts, one for the option that requested STDIN (others are None).

    Raises:
        UsageError: If multiple options request STDIN simultaneously.
    """
    wants: list[StdinUse] = []
    if any(x == "-" for x in files_from):
        wants.append(StdinUse.FILES_FROM)
    if any(x == "-" for x in include_from):
        wants.append(StdinUse.INCLUDE_FROM)
    if any(x == "-" for x in exclude_from):
        wants.append(StdinUse.EXCLUDE_FROM)

    if len(wants) > 1:
        raise TopmarkUsageError(
            f"Only one of --files-from/--include-from/--exclude-from may read from STDIN ('-'). "
            f"Requested: {', '.join(wants)}"
        )

    text_files = text_includes = text_excludes = None
    if wants:
        text = stdin_text
        if text is None:
            text = click.get_text_stream("stdin").read()
        # Treat empty as empty list; keep it simple (no error)
        # (No need to check for None, as text is always a string here)
        if wants[0] == StdinUse.FILES_FROM:
            text_files = text
        elif wants[0] == StdinUse.INCLUDE_FROM:
            text_includes = text
        else:
            text_excludes = text
    return text_files, text_includes, text_excludes


# Remove '-' entries so downstream resolvers never try to open STDIN as a file.
def strip_dash_sentinels(
    files_from: Iterable[str],
    include_from: Iterable[str],
    exclude_from: Iterable[str],
) -> tuple[list[str], list[str], list[str]]:
    """Remove '-' entries so downstream resolvers never try to open STDIN as a file."""
    return (
        [x for x in files_from if x != "-"],
        [x for x in include_from if x != "-"],
        [x for x in exclude_from if x != "-"],
    )


def extend_with_stdin_lines(target: list[str], stdin_text: str | None) -> list[str]:
    """Extend `target` with non-empty, non-comment lines from `stdin_text`."""
    if stdin_text:
        target.extend(split_nonempty_lines(stdin_text))
    return target


def split_nonempty_lines(text: str | None) -> list[str]:
    """Split text into non-empty, non-comment lines.

    Lines are stripped; blank lines and lines starting with '#' are ignored.

    Args:
        text: Raw text (possibly None).

    Returns:
        List of cleaned lines.
    """
    if not text:
        return []
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


class ColorMode(str, Enum):
    """User intent for colorized terminal output."""

    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


def resolve_color_mode(
    *,
    cli_mode: ColorMode | None,
    output_format: str | None,
    stdout_isatty: bool | None = None,
) -> bool:
    """Determine whether color output should be enabled.

    Args:
        cli_mode: Explicit color mode from CLI options (auto, always, never).
        output_format: Output format string, e.g. "json", "ndjson".
        stdout_isatty: Whether stdout is a TTY; if None, auto-detected.

    Returns:
        True if color output should be enabled, False otherwise.

    Behavior:
        Disables color for JSON/NDJSON output formats.
        Honors --color and --no-color CLI flags.
        Honors FORCE_COLOR and NO_COLOR environment variables.
        Defaults to enabling color if stdout is a TTY.
    """
    if output_format and output_format.lower() in {"json", "ndjson"}:
        return False
    if cli_mode == ColorMode.ALWAYS:
        return True
    if cli_mode == ColorMode.NEVER:
        return False
    force_color = os.getenv("FORCE_COLOR")
    if force_color and force_color != "0":
        return True
    if os.getenv("NO_COLOR") is not None:
        return False
    if stdout_isatty is None:
        try:
            stdout_isatty = sys.stdout.isatty()
        except Exception:
            stdout_isatty = False
    return bool(stdout_isatty)


def common_color_options(f: Callable[P, R]) -> Callable[P, R]:
    """Adds --color and --no-color options to a command.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function with color options added.

    Behavior:
        Adds --color with choices (auto, always, never).
        Adds --no-color flag that disables color output.
        These options control colorized terminal output.
    """
    f = click.option(
        "--color",
        "color_mode",
        type=click.Choice([m.value for m in ColorMode]),
        default=None,
        help="Color output: auto (default), always, or never.",
    )(f)
    f = click.option(
        "--no-color",
        "no_color",
        is_flag=True,
        help="Disable color output (equivalent to --color=never).",
    )(f)
    return f


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

    return click.option(
        *names,
        dest,
        hidden=True,
        expose_value=False,
        is_eager=True,
        multiple=True,
        callback=trap_underscored_option,
    )


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
        type=EnumChoiceParam(HeaderOutputFormat),
        help=f"Select the header format ({', '.join(e.value for e in HeaderOutputFormat)}).",
    )(f)
    f = underscored_trap_option("--header_format")(f)

    return f
