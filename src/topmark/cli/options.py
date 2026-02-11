# topmark:header:start
#
#   project      : TopMark
#   file         : options.py
#   file_relpath : src/topmark/cli/options.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Common CLI option utilities for the Click-based TopMark prototype.

This module centralizes reusable options (verbosity, color) and their
resolution logic, so commands and groups can stay thin. The helpers here are
Click-aware.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, ParamSpec, TypeVar

import click
from click.core import ParameterSource

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.errors import TopmarkUsageError
from topmark.cli.keys import CliOpt
from topmark.cli_shared.color import ColorMode
from topmark.config.logging import TRACE_LEVEL, get_logger
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey
from topmark.rendering.formats import HeaderOutputFormat

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from topmark.config.logging import TopmarkLogger

P = ParamSpec("P")
R = TypeVar("R")

# Custom verbosity levels, mapped to standard logging levels
LOG_LEVELS: dict[str, int] = {
    "TRACE": TRACE_LEVEL,  # Custom TRACE (5) sits below logging.DEBUG.
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


logger: TopmarkLogger = get_logger(__name__)


# Helper: allow comma-separated multi-value options
def _split_csv_multi_option(
    _ctx: click.Context,
    _param: click.Parameter,
    value: tuple[str, ...],
) -> tuple[str, ...]:
    """Allow comma-separated lists for `multiple=True` options.

    This callback supports both:
      - repeating the option: `--file-type py --file-type toml`
      - comma-separated values: `--file-type py,toml`

    It is intentionally strict/simple:
      - strips whitespace around tokens
      - ignores empty tokens (e.g., trailing commas)

    Args:
        _ctx: Click context (unused).
        _param: Click parameter (unused).
        value: Collected option values (one entry per occurrence).

    Returns:
        A flattened tuple of tokens.
    """
    out: list[str] = []
    for raw in value:
        # Split each occurrence on commas; allow users to mix styles.
        for part in raw.split(","):
            token: str = part.strip()
            if not token:
                continue
            out.append(token)
    return tuple(out)


def resolve_verbosity(verbose_count: int, quiet_count: int) -> int:
    """Resolve the final logging level based on verbose and quiet counts.

    Args:
        verbose_count: Number of times the verbose flag (-v) is passed.
        quiet_count: Number of times the quiet flag (-q) is passed.

    Returns:
        The verbosity level as an integer.

    Raises:
        TopmarkUsageError: If both verbose and quiet flags are used simultaneously.

    Behavior:
        The --verbose and --quiet options are mutually exclusive.
    """
    # They are mutually exclusive
    if verbose_count > 0 and quiet_count > 0:
        raise TopmarkUsageError("The '--verbose' and '--quiet' options are mutually exclusive.")

    verbosity_level: int = verbose_count - quiet_count
    return verbosity_level


#: Click context settings to allow Black-style extra args and unknown options.
CONTEXT_SETTINGS: dict[str, list[str] | bool] = {
    "help_option_names": ["-h", CliOpt.HELP],
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
        CliOpt.VERBOSE,
        "-v",
        count=True,
        help="Increase verbosity. Specify up to twice for more detail.",
    )(f)
    f = click.option(
        CliOpt.QUIET,
        "-q",
        count=True,
        help="Suppress output. Specify up to twice for even less.",
    )(f)
    return f


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
        CliOpt.COLOR_MODE,
        ArgKey.COLOR_MODE,
        type=click.Choice([m.value for m in ColorMode]),
        default=None,
        help="Color output: auto (default), always, or never.",
    )(f)
    f = click.option(
        CliOpt.NO_COLOR_MODE,
        ArgKey.NO_COLOR_MODE,
        is_flag=True,
        help=f"Disable color output (equivalent to {CliOpt.COLOR_MODE}=never).",
    )(f)
    return f


def common_ui_options(f: Callable[P, R]) -> Callable[P, R]:
    """Convenience decorator (verbosity + color mode).

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function with color options added.

    Behavior:
        Adds --verbose and --quiet options (mutually exclusive).
        Adds --color with choices (auto, always, never).
        Adds --no-color flag that disables color output.
    """
    f = common_verbose_options(f)
    f = common_color_options(f)
    return f


def common_output_format_options(f: Callable[P, R]) -> Callable[P, R]:
    """Apply common output format options.

    Adds the ``--output-format`` option which accepts OutputFormat values for human use (``text``,
    ``markdown``) and machine  formats (``json``, ``ndjson``). If not set, it will be resolved to
    ``text`` (ANSI-capable).

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = click.option(
        CliOpt.OUTPUT_FORMAT,
        ArgKey.OUTPUT_FORMAT,
        type=EnumChoiceParam(OutputFormat),
        default=None,
        help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
    )(f)
    f = underscored_trap_option("--output_format")(f)
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
        CliOpt.STDIN_FILENAME,
        ArgKey.STDIN_FILENAME,
        type=str,
        default=None,
        help=(
            "Assumed filename when reading a single file's content from STDIN via '-' (dash). "
            "Required when '-' is provided as a PATH."
        ),
    )(f)

    # Option for reading candidate file paths from files
    f = click.option(
        CliOpt.FILES_FROM,
        ArgKey.FILES_FROM,
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
        CliOpt.INCLUDE_PATTERNS,
        "-i",
        ArgKey.INCLUDE_PATTERNS,
        multiple=True,
        help="Filter: keep only files matching these glob patterns (intersection).",
    )(f)

    f = click.option(
        CliOpt.INCLUDE_FROM,
        ArgKey.INCLUDE_FROM,
        type=str,  # Ensure '-' passes through untouched
        multiple=True,
        help="Filter: read include glob patterns from file(s) (use '-' for STDIN).",
    )(f)
    f = underscored_trap_option("--include_from")(f)

    f = click.option(
        CliOpt.EXCLUDE_PATTERNS,
        "-e",
        ArgKey.EXCLUDE_PATTERNS,
        multiple=True,
        help="Filter: remove files matching these glob patterns (subtraction).",
    )(f)

    f = click.option(
        CliOpt.EXCLUDE_FROM,
        ArgKey.EXCLUDE_FROM,
        type=str,  # Ensure '-' passes through untouched
        multiple=True,
        help="Filter: read exclude glob patterns from file(s) (use '-' for STDIN).",
    )(f)
    f = underscored_trap_option("--exclude_from")(f)

    f = click.option(
        CliOpt.INCLUDE_FILE_TYPES,
        CliOpt.INCLUDE_FILE_TYPE,
        "-t",
        ArgKey.INCLUDE_FILE_TYPES,
        multiple=True,
        callback=_split_csv_multi_option,
        help=(
            "Filter: restrict to given file types. Applied after path include/exclude filtering. "
            "May be repeated and/or given as a comma-separated list."
        ),
    )(f)
    f = underscored_trap_option("--include_file_types", "--include_file_type")(f)

    f = click.option(
        CliOpt.EXCLUDE_FILE_TYPES,
        CliOpt.EXCLUDE_FILE_TYPE,
        "-T",
        ArgKey.EXCLUDE_FILE_TYPES,
        multiple=True,
        callback=_split_csv_multi_option,
        help=(
            "Filter: exclude given file types. Applied after path include/exclude filtering. "
            "May be repeated and/or given as a comma-separated list."
        ),
    )(f)
    f = underscored_trap_option("--exclude_file_types", "--exclude_file_type")(f)

    # TODO: consider adding --extension filter, add a force-handle-file-as-XXX option

    f = click.option(
        CliOpt.RELATIVE_TO,
        ArgKey.RELATIVE_TO,
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
        TopmarkUsageError: If multiple options request STDIN simultaneously.
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
            f"Only one of {CliOpt.FILES_FROM} / {CliOpt.INCLUDE_FROM} / {CliOpt.EXCLUDE_FROM} "
            f"may read from STDIN ('-'). Requested: {', '.join(wants)}"
        )

    text_files: str | None = None
    text_includes: str | None = None
    text_excludes: str | None = None
    text: str | None = None
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
        s: str = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def trap_underscored_option(ctx: click.Context, param: click.Option, _value: object) -> None:
    """Raise a helpful error for underscored long options (e.g., --exclude_from).

    Runs during option parsing (is_eager=True) so we can show a friendly hint
    instead of the generic "No such option" error.
    """
    # Only trigger if the user actually typed the option
    name: str | None = param.name or None
    try:
        src: ParameterSource | None = ctx.get_parameter_source(name) if name else None
    except (AttributeError, RuntimeError, click.ClickException):
        src = None
    if src is not ParameterSource.COMMANDLINE:
        return

    bad: str = param.opts[0] if param.opts else "--?"
    suggestion: str = bad.replace("_", "-")
    raise click.UsageError(f"Unknown option: {bad}. Did you mean {suggestion}?")


def underscored_trap_option(*names: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Register hidden underscored spellings that raise a helpful error.

    This wraps `click.option` with common settings for underscored
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

    Raises:
        ValueError: if option name was not provided

    Returns:
        A decorator compatible with Click's option stacking.
    """
    if not names:
        raise ValueError("underscored_trap_option requires at least one option name")

    first: str = names[0]
    # Create a unique, non-conflicting Python destination name for the hidden option
    dest: str = f"_trap_{first.lstrip('-').replace('-', '_')}"

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
        CliOpt.VERBOSE,
        "-v",
        ArgKey.VERBOSE,
        type=int,
        count=True,
        help="Increase log verbosity (can be repeated)",
    )(f)
    f = click.option(
        CliOpt.QUIET,
        "-q",
        ArgKey.QUIET,
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
        CliOpt.NO_CONFIG,
        ArgKey.NO_CONFIG,
        is_flag=True,
        help="Ignore local project config files (only use defaults).",
    )(f)
    f = underscored_trap_option("--no_config")(f)
    f = click.option(
        CliOpt.CONFIG_PATHS,
        ArgKey.CONFIG_PATHS,
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
        f"{CliOpt.ALIGN_FIELDS}/{CliOpt.NO_ALIGN_FIELDS}",
        ArgKey.ALIGN_FIELDS,
        is_flag=True,
        default=None,
        help="Align header fields with colons.",
    )(f)
    f = underscored_trap_option("--align_fields")(f)
    f = underscored_trap_option("--no_align_fields")(f)
    f = click.option(
        CliOpt.HEADER_FORMAT,
        ArgKey.HEADER_FORMAT,
        type=EnumChoiceParam(HeaderOutputFormat),
        help=f"Select the header format ({', '.join(e.value for e in HeaderOutputFormat)}).",
    )(f)
    f = underscored_trap_option("--header_format")(f)

    return f
