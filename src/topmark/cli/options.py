# topmark:header:start
#
#   project      : TopMark
#   file         : options.py
#   file_relpath : src/topmark/cli/options.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Common Click option decorators and parsing utilities for TopMark.

This module centralizes reusable Click option definitions and CLI-focused parsing
utilities so command implementations can remain thin and consistent.

Structure
---------
- Small parsing helpers for `--*-from` inputs and verbosity resolution.
- Underscored spelling traps (e.g. `--include_from` → hint `--include-from`).
- Reusable option-decorator builders used by CLI commands.

Conventions
-----------
- Public decorators are named `common_*_options` or `<domain>_*_options`.
- Parsing helpers are small, typed, and import-safe.
- Long option spellings come from [`topmark.cli.keys.CliOpt`][topmark.cli.keys.CliOpt].
- Short option spellings come from [`topmark.cli.keys.CliShortOpt`][topmark.cli.keys.CliShortOpt].
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from typing import ParamSpec
from typing import TypedDict
from typing import TypeVar

import click
from click.core import ParameterSource
from typing_extensions import NotRequired
from typing_extensions import Unpack

from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.console.color import ColorMode
from topmark.cli.errors import TopmarkCliUsageError
from topmark.cli.keys import CliOpt
from topmark.cli.keys import CliShortOpt
from topmark.config.policy import EmptyInsertMode
from topmark.config.policy import HeaderMutationMode
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey
from topmark.core.logging import get_logger
from topmark.pipeline.reporting import ReportScope

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable

    from topmark.core.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)

#: Typed Click option deccorators consume and return `Callable[_P, _R]`
_P = ParamSpec("_P")
_R = TypeVar("_R")

#: Click context settings for groups.
GROUP_CONTEXT_SETTINGS: dict[str, list[str] | bool] = {
    "help_option_names": [
        CliShortOpt.HELP,
        CliOpt.HELP,
    ],
}

#: Click context settings to allow Black-style extra args and unknown options.
PATH_COMMAND_CONTEXT_SETTINGS: dict[str, list[str] | bool] = {
    **GROUP_CONTEXT_SETTINGS,
    "ignore_unknown_options": True,
    "allow_extra_args": True,
}


class StdinUse(str, Enum):
    """Identify which `--*-from` option (if any) consumes STDIN.

    Values:
        NONE: Default; no `--*-from` option consumes STDIN.
        FILES_FROM: `--files-from -` consumes STDIN (newline-delimited file paths).
        INCLUDE_FROM: `--include-from -` consumes STDIN (newline-delimited glob patterns).
        EXCLUDE_FROM: `--exclude-from -` consumes STDIN (newline-delimited glob patterns).
    """

    NONE = "none"  # default: positional + --files-from (+ include/exclude filters)
    FILES_FROM = "files-from"  # a single virtual file: '-' + --stdin-filename
    INCLUDE_FROM = "include-from"
    EXCLUDE_FROM = "exclude-from"


@dataclass(frozen=True, kw_only=True, slots=True)
class FromOptionValues:
    """Values supplied through `--*-from` options.

    Attributes:
        files_from: Values passed through `--files-from`.
        include_from: Values passed through `--include-from`.
        exclude_from: Values passed through `--exclude-from`.
    """

    files_from: list[str]
    include_from: list[str]
    exclude_from: list[str]


@dataclass(frozen=True, kw_only=True, slots=True)
class FromOptionStdinText:
    """STDIN text routed to at most one `--*-from -` option.

    Attributes:
        files_from: Raw STDIN text for `--files-from -`, or `None`.
        include_from: Raw STDIN text for `--include-from -`, or `None`.
        exclude_from: Raw STDIN text for `--exclude-from -`, or `None`.
    """

    files_from: str | None = None
    include_from: str | None = None
    exclude_from: str | None = None


class _ClickOptionKwargs(TypedDict, total=True):
    """Provide typing for the `click.Option` kwargs.

    Because we're unpacking kwargs, each key is optional in practice.
    Mark all fields explicitly as `NotRequired` for easier reading.
    """

    cls: NotRequired[type[click.Option] | None]
    count: NotRequired[bool]
    is_flag: NotRequired[bool]
    multiple: NotRequired[bool]
    show_default: NotRequired[bool]
    hidden: NotRequired[bool]
    help: NotRequired[str | None]
    metavar: NotRequired[str | None]
    type: NotRequired[object]
    default: NotRequired[object]
    callback: NotRequired[object]


# ---- Low-level parsing helpers ----


def split_nonempty_lines(text: str | None) -> list[str]:
    """Split text into non-empty, non-comment lines.

    Lines are stripped. Blank lines and lines starting with `#` are ignored.

    Args:
        text: Raw text (possibly None).

    Returns:
        Cleaned, non-empty lines.
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


def extend_with_stdin_lines(target: list[str], stdin_text: str | None) -> list[str]:
    """Extend `target` with non-empty, non-comment lines from STDIN text.

    Args:
        target: List to extend.
        stdin_text: Raw text from STDIN (possibly None).

    Returns:
        The same list instance for convenience.
    """
    if stdin_text:
        target.extend(split_nonempty_lines(stdin_text))
    return target


def strip_dash_sentinels(
    files_from: Iterable[str],
    include_from: Iterable[str],
    exclude_from: Iterable[str],
) -> FromOptionValues:
    """Remove '-' sentinels so downstream code never treats STDIN as a file path.

    Args:
        files_from: Values passed via `--files-from` (may include '-').
        include_from: Values passed via `--include-from` (may include '-').
        exclude_from: Values passed via `--exclude-from` (may include '-').

    Returns:
        Values from each `--*-from` option with `'-'` removed.
    """
    return FromOptionValues(
        files_from=[x for x in files_from if x != "-"],
        include_from=[x for x in include_from if x != "-"],
        exclude_from=[x for x in exclude_from if x != "-"],
    )


def extract_stdin_for_from_options(
    files_from: Iterable[str],
    include_from: Iterable[str],
    exclude_from: Iterable[str],
    stdin_text: str | None = None,
) -> FromOptionStdinText:
    """Return raw STDIN text for at most one `--*-from -` option.

    If one of the options contains `'-'`, this reads STDIN (unless `stdin_text`
    is provided) and returns that text for the requesting option. If multiple
    `--*-from` options request STDIN, a usage error is raised.

    Args:
        files_from: Values passed via `--files-from` (may include '-').
        include_from: Values passed via `--include-from` (may include '-').
        exclude_from: Values passed via `--exclude-from` (may include '-').
        stdin_text: Optional pre-read STDIN content (useful for tests).

    Returns:
        Routed STDIN text for the requesting `--*-from -` option. At most one field
        is non-`None`.

    Raises:
        TopmarkCliUsageError: If multiple options request STDIN simultaneously.
    """
    wants: list[StdinUse] = []
    if any(x == "-" for x in files_from):
        wants.append(StdinUse.FILES_FROM)
    if any(x == "-" for x in include_from):
        wants.append(StdinUse.INCLUDE_FROM)
    if any(x == "-" for x in exclude_from):
        wants.append(StdinUse.EXCLUDE_FROM)

    if len(wants) > 1:
        raise TopmarkCliUsageError(
            f"Only one of {CliOpt.FILES_FROM} / {CliOpt.INCLUDE_FROM} / {CliOpt.EXCLUDE_FROM} "
            f"may read from STDIN ('-'). Requested: {', '.join(w.value for w in wants)}"
        )

    text_files: str | None = None
    text_includes: str | None = None
    text_excludes: str | None = None

    if wants:
        text: str = stdin_text if stdin_text is not None else click.get_text_stream("stdin").read()
        # Treat empty as empty list; keep it simple (no error)
        # (No need to check for None, as text is always a string here)
        if wants[0] == StdinUse.FILES_FROM:
            text_files = text
        elif wants[0] == StdinUse.INCLUDE_FROM:
            text_includes = text
        else:
            text_excludes = text

    return FromOptionStdinText(
        files_from=text_files,
        include_from=text_includes,
        exclude_from=text_excludes,
    )


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
        Flattened tuple of tokens.
    """
    out: list[str] = []
    for raw in value:
        # Split each occurrence on commas; allow users to mix styles.
        for part in raw.split(","):
            token: str = part.strip()
            if token:
                out.append(token)
    return tuple(out)


def normalize_verbosity(verbose_count: int) -> int:
    """Normalize an integer verbosity level from `-v/--verbose` counts.

    Args:
        verbose_count: Number of times `-v/--verbose` is passed.

    Returns:
        Normalized verbosity level in the range 0..2.
    """
    return min(2, max(0, verbose_count))


# ---- Trap infrastructure ----


def _trap_underscored_option(ctx: click.Context, param: click.Option, _value: object) -> None:
    """Raise a helpful error for underscored long options (e.g., `--exclude_from`).

    This runs eagerly during option parsing and uses Click's `ParameterSource`
    to avoid false positives (i.e., do not trigger unless the user typed the
    underscored spelling explicitly).

    Args:
        ctx: Click context.
        param: The hidden trap option being processed.
        _value: Parsed option value (ignored).

    Raises:
        click.UsageError: Always, when the trap option was provided on the CLI.
    """
    name: str | None = param.name or None
    try:
        src: ParameterSource | None = ctx.get_parameter_source(name) if name else None
    except (AttributeError, RuntimeError, click.ClickException):
        src = None

    if src is not ParameterSource.COMMANDLINE:
        return

    bad: str = param.opts[0] if param.opts else "--?"
    suggestion: str = bad.replace("_", "-")
    raise click.UsageError(f"Unknown option: '{bad}'. Did you mean '{suggestion}'?")


def option_with_underscore_traps(
    *param_decls: str,
    **attrs: Unpack[_ClickOptionKwargs],
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Like `click.option`, but also traps underscored spellings.

    For each canonical long option declaration of the form `--foo-bar`, this helper
    also registers a hidden eager flag `--foo_bar` that raises a helpful error
    suggesting the hyphenated spelling.

    The trap is attached alongside the real option so call sites don't need to
    remember to register traps separately.

    Trap options are always flags, even when the canonical option takes a value.
    This ensures underscored spellings are rejected immediately instead of being
    parsed as value-taking options.

    Args:
        *param_decls: Click option declarations (e.g. `"--verbose"`, `"-v"`).
        **attrs: Keyword arguments forwarded to `click.option`.

    Returns:
        A Click option decorator.
    """
    canonical_longs: list[str] = [
        d
        for d in param_decls
        if d.startswith("--")  # Only long options
        and ("/" not in d)  # Keep paired flags: don't generate underscore traps for them
        and ("_" not in d)
        and ("-" in d[2:])
    ]
    trap_longs: list[str] = ["--" + d[2:].replace("-", "_") for d in canonical_longs]

    real_decorator: Callable[[Callable[_P, _R]], Callable[_P, _R]] = click.option(
        *param_decls,
        **attrs,
    )

    if not trap_longs:
        return real_decorator

    # Deterministic hidden destination; avoid collisions with real dest names.
    key: str = canonical_longs[0][2:].replace("-", "_")
    trap_dest: str = f"_trap__{key}"

    trap_decorator: Callable[[Callable[_P, _R]], Callable[_P, _R]] = click.option(
        *trap_longs,
        trap_dest,
        hidden=True,
        expose_value=False,
        is_eager=True,
        is_flag=True,
        callback=_trap_underscored_option,
    )

    def decorator(f: Callable[_P, _R]) -> Callable[_P, _R]:
        f = trap_decorator(f)
        f = real_decorator(f)
        return f

    return decorator


def option_with_hidden_aliases_and_underscore_traps(
    *param_decls: str,
    hidden_aliases: tuple[str, ...],
    multiple: bool = False,
    callback: Callable[..., object] | None = None,
    help: str | None = None,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Like `option_with_underscore_traps`, with hidden compatibility aliases.

    Hidden aliases are registered as separate hidden Click options that write to
    the same destination as the visible option. This keeps the compatibility
    aliases accepted by Click while omitting them from Click and Rich Click help
    output.

    This helper intentionally exposes only the option attributes currently
    needed by file-type filters. Keeping the signature narrow avoids ambiguous
    `TypedDict` unpacking for the forced `hidden=True` alias option.

    Args:
        *param_decls: Visible Click option declarations. The declarations must
            include an explicit destination name.
        hidden_aliases: Compatibility aliases accepted but hidden from help.
        multiple: Whether the visible and hidden options may be repeated.
        callback: Optional Click callback applied to parsed option values.
        help: Human-facing help text for the visible option.

    Returns:
        A Click option decorator.

    Raises:
        ValueError: If `param_decls` does not include an explicit destination.
    """
    destination_names: list[str] = [d for d in param_decls if not d.startswith("-")]
    if not destination_names:
        raise ValueError("hidden alias options require an explicit destination name")

    destination_name: str = destination_names[-1]
    visible_decorator: Callable[[Callable[_P, _R]], Callable[_P, _R]] = (
        option_with_underscore_traps(
            *param_decls,
            multiple=multiple,
            callback=callback,
            help=help,
        )
    )
    hidden_alias_decorator: Callable[[Callable[_P, _R]], Callable[_P, _R]] = (
        option_with_underscore_traps(
            *hidden_aliases,
            destination_name,
            hidden=True,
            multiple=multiple,
            callback=callback,
            help=None,
        )
    )

    def decorator(f: Callable[_P, _R]) -> Callable[_P, _R]:
        decorated: Callable[_P, _R] = hidden_alias_decorator(f)
        decorated = visible_decorator(decorated)
        return decorated

    return decorator


def enum_value_help_text(
    enum_cls: type[Enum],
    *,
    prefix: str = "",
    default: Enum | str | None = None,
    suffix: str | None = None,
) -> str:
    """Render CLI-facing help text for enum option values.

    CLI help prefers kebab-case values for readability. TopMark's
    configuration, Python API enum values, and machine-readable output use
    canonical underscore values when enum members are defined with underscores.
    This helper renders the CLI-facing value list, marks an optional default,
    and appends a short underscore/canonical-value note only when needed.

    Args:
        enum_cls: Enum class whose members expose string values.
        prefix: Optional text placed before the rendered value list.
        default: Optional enum member or raw value to mark as the default.
        suffix: Optional sentence appended after the alias/canonical-value note.

    Returns:
        Help text suitable for inclusion in a Click option description.
    """
    default_value: str | None
    if isinstance(default, Enum):
        default_value = str(default.value)
    elif default is None:
        default_value = None
    else:
        default_value = str(default)

    rendered_values: list[str] = []
    underscore_values: list[str] = []

    for member in enum_cls:
        raw_value: str = str(member.value)
        rendered_value: str = raw_value.replace("_", "-")
        if raw_value == default_value:
            rendered_value = f"'{rendered_value}' (default)"
        else:
            rendered_value = f"'{rendered_value}'"
        rendered_values.append(rendered_value)
        if "_" in raw_value:
            underscore_values.append(raw_value)

    text: str = f"Accepted values: {', '.join(rendered_values)}."
    if prefix:
        text = f"{prefix} {text}"

    if underscore_values:
        text += (
            f" CLI also accepts underscore forms ({', '.join(underscore_values)}); "
            "config, API, and machine-readable output use underscore values."
        )

    if suffix:
        text += f" {suffix}"

    return text


# ---- Option decorators ----


def common_text_output_verbosity_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Adds --verbose option to a command.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function with verbosity option added.

    Behavior:
        Adds count-based `-v/--verbose` detail controls for text output.
    """
    f = option_with_underscore_traps(
        CliOpt.VERBOSE,
        ArgKey.VERBOSITY,
        CliShortOpt.VERBOSE,
        count=True,
        help="Increase TEXT output detail. Repeat once for full detail.",
    )(f)
    return f


def common_text_output_quiet_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Adds --quiet option to a command.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function with quiet option added.

    Behavior:
        Adds boolean `-q/--quiet` suppression for text output.
    """
    f = option_with_underscore_traps(
        CliOpt.QUIET,
        ArgKey.QUIET,
        CliShortOpt.QUIET,
        is_flag=True,
        default=False,
        help="Suppress human (TEXT) output and rely on exit status only.",
    )(f)
    return f


def common_color_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
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
    f = option_with_underscore_traps(
        CliOpt.COLOR_MODE,
        ArgKey.COLOR_MODE,
        type=EnumChoiceParam(
            ColorMode,
            case_sensitive=False,
            kebab_case=True,
        ),
        default=None,
        help=enum_value_help_text(
            ColorMode,
            prefix="Color output for text format.",
            default=ColorMode.AUTO,
        ),
    )(f)
    f = option_with_underscore_traps(
        CliOpt.NO_COLOR_MODE,
        ArgKey.NO_COLOR_MODE,
        is_flag=True,
        help="Disable color output for text format "
        f"(equivalent to {CliOpt.COLOR_MODE}={ColorMode.NEVER.value}).",
    )(f)
    return f


def common_output_format_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common output format options.

    Adds the ``--output-format`` option which accepts OutputFormat values for human use
    (``text``, ``markdown``) and machine-readable formats (``json``, ``ndjson``).
    If not set, it will be resolved to ``text`` (ANSI-capable).

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.OUTPUT_FORMAT,
        ArgKey.OUTPUT_FORMAT,
        type=EnumChoiceParam(
            OutputFormat,
            case_sensitive=False,
            kebab_case=True,
        ),
        default=None,
        help=enum_value_help_text(
            OutputFormat,
            prefix="Output format.",
            default=OutputFormat.TEXT,
        ),
    )(f)
    return f


def common_header_field_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common header field selection and definition options.

    Adds the folloiwng header field options: ``--header-fields``,
    ``--field-values``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.HEADER_FIELDS,
        ArgKey.HEADER_FIELDS,
        default=None,
        help="Header fields (ordered list of built-in or custom header fields).",
    )(f)
    f = option_with_underscore_traps(
        CliOpt.FIELD_VALUES,
        ArgKey.FIELD_VALUES,
        default=None,
        help="Define or override header field values (for example header_field=field_value pairs).",
    )(f)
    return f


def common_include_exclude_from_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common file selection and filtering options.

    Adds the following file source options: ``--include-from``, ``--exclude-from``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.INCLUDE_FROM,
        ArgKey.INCLUDE_FROM,
        type=str,  # Ensure '-' passes through untouched
        multiple=True,
        help="Filter: read include glob patterns from file(s) "
        "(use '-' for STDIN). May be repeated.",
    )(f)

    f = option_with_underscore_traps(
        CliOpt.EXCLUDE_FROM,
        ArgKey.EXCLUDE_FROM,
        type=str,  # Ensure '-' passes through untouched
        multiple=True,
        help="Filter: read exclude glob patterns from file(s) "
        "(use '-' for STDIN). May be repeated.",
    )(f)

    return f


def common_files_from_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common file selection and filtering options.

    Adds the following file source options: ``--files-from``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    # Option for reading candidate file paths from files
    f = option_with_underscore_traps(
        CliOpt.FILES_FROM,
        ArgKey.FILES_FROM,
        type=str,  # Ensure '-' passes through untouched
        multiple=True,
        help=(
            "Source: add candidate files by reading newline-delimited paths from file(s) "
            "(use '-' for STDIN). "
            "These paths are added to positional PATHS/globs before filtering."
        ),
    )(f)

    return f


def config_dump_files_from_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply config dump file selection and filtering options.

    Adds the following file source options: ``--files-from``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    # Option for reading candidate file paths from files (for config dump)
    f = option_with_underscore_traps(
        CliOpt.FILES_FROM,
        ArgKey.FILES_FROM,
        type=str,  # Ensure '-' passes through untouched
        multiple=True,
        help=(
            "Accept newline-delimited paths from file(s) for compatibility "
            "(use '-' for STDIN). "
            "Listed paths do not affect the dumped configuration."
        ),
    )(f)

    return f


def common_stdin_content_mode_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common file selection and filtering options.

    Adds option ``--stdin-filename`` when processing file contents from STDIN.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    # Option for STDIN content mode (inserted before --files-from)
    f = option_with_underscore_traps(
        CliOpt.STDIN_FILENAME,
        ArgKey.STDIN_FILENAME,
        type=str,
        default=None,
        help=(
            "Assumed filename when reading a single file's content from STDIN via '-' (dash). "
            "Required when '-' is provided as a PATH."
        ),
    )(f)

    return f


def common_file_filtering_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common file selection and filtering pattern options.

    Adds file inclusion / exclusion pattern options: ``--include``, ``--exclude``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.INCLUDE_PATTERNS,
        CliShortOpt.INCLUDE_PATTERNS,
        ArgKey.INCLUDE_PATTERNS,
        multiple=True,
        help="Filter: include only files matching these glob patterns (intersection). "
        "May be repeated.",
    )(f)

    f = option_with_underscore_traps(
        CliOpt.EXCLUDE_PATTERNS,
        CliShortOpt.EXCLUDE_PATTERNS,
        ArgKey.EXCLUDE_PATTERNS,
        multiple=True,
        help="Filter: exclude files matching these glob patterns (subtraction). May be repeated.",
    )(f)

    return f


def common_file_type_filtering_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common file type selection and filtering options.

    Adds file type filtering options: ``--include-file-types``, ``--exclude-file-types``.
    The singular spellings remain accepted as hidden compatibility aliases.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_hidden_aliases_and_underscore_traps(
        CliOpt.INCLUDE_FILE_TYPES,
        CliShortOpt.INCLUDE_FILE_TYPES,
        ArgKey.INCLUDE_FILE_TYPES,
        hidden_aliases=(CliOpt.INCLUDE_FILE_TYPE,),
        multiple=True,
        callback=_split_csv_multi_option,
        help=(
            "Filter: restrict to given file types. "
            "Applied after path include/exclude filtering. "
            "May be repeated and/or given as a comma-separated list."
        ),
    )(f)

    f = option_with_hidden_aliases_and_underscore_traps(
        CliOpt.EXCLUDE_FILE_TYPES,
        CliShortOpt.EXCLUDE_FILE_TYPES,
        ArgKey.EXCLUDE_FILE_TYPES,
        hidden_aliases=(CliOpt.EXCLUDE_FILE_TYPE,),
        multiple=True,
        callback=_split_csv_multi_option,
        help=(
            "Filter: exclude given file types. "
            "Applied after path include/exclude filtering. "
            "May be repeated and/or given as a comma-separated list."
        ),
    )(f)

    return f


def common_apply_and_write_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common file selection and filtering options.

    Adds options such as ``--apply``, ``--write-mode``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.APPLY_CHANGES,
        ArgKey.APPLY_CHANGES,
        is_flag=True,
        help="Write changes to files (off by default).",
    )(f)

    f = option_with_underscore_traps(
        CliOpt.WRITE_MODE,
        ArgKey.WRITE_MODE,
        type=click.Choice(["atomic", "inplace", "stdout"], case_sensitive=False),
        help=(
            "Select write strategy: 'atomic' (safe, default), "
            "'inplace' (fast, less safe), or 'stdout' (emit result to standard output)."
        ),
    )(f)

    return f


def render_diff_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply diff rendering options.

    Adds the following option: ``--diff``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.RENDER_DIFF,
        ArgKey.RENDER_DIFF,
        is_flag=True,
        help="Show unified diffs (human output only).",
    )(f)

    return f


def pipeline_reporting_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply summary/reporting options for pipeline-style commands.

    Adds the following options:
        - ``--summary``: show outcome counts instead of per-file details.
        - ``--report``: control which entries appear in **human per-file**
          output.

    Notes:
        `--report` is a human-facing per-file listing policy. It is ignored for
        summary mode and machine-readable output.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.RESULTS_SUMMARY_MODE,
        ArgKey.RESULTS_SUMMARY_MODE,
        is_flag=True,
        help="Show summary of outcome counts instead of per-file details.",
    )(f)

    f = option_with_underscore_traps(
        CliOpt.REPORT,
        ArgKey.REPORT_SCOPE,
        type=EnumChoiceParam(
            ReportScope,
            case_sensitive=False,
            kebab_case=True,
        ),
        default=ReportScope.ACTIONABLE,
        help=enum_value_help_text(
            ReportScope,
            prefix=(
                "Reporting scope for human per-file output. "
                "Ignored for summary mode and machine-readable formats."
            ),
            default=ReportScope.ACTIONABLE,
            suffix=(
                "Use 'actionable' to list would-change results and other attention-worthy states; "
                "'noncompliant' to list actionable results plus unsupported entries; "
                "'all' to list every processed result, including unchanged entries. "
            ),
        ),
    )(f)

    return f


def registry_details_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply details mode output options for registry commands.

    Adds the following option: ``--long``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.SHOW_DETAILS,
        ArgKey.SHOW_DETAILS,
        CliShortOpt.SHOW_DETAILS,
        is_flag=True,
        help="Show extended information (extensions, filenames, patterns, skip policy, "
        "header policy).",
    )(f)

    return f


def config_strict_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Add config strictness override options.

    The CLI flags override the effective `[config].strict` value for the current run.
    """
    f = option_with_underscore_traps(
        f"{CliOpt.STRICT}/{CliOpt.NO_STRICT}",
        ArgKey.STRICT,
        is_flag=True,
        default=None,
        help="Fail if any warnings are present (in addition to errors).",
    )(f)

    return f


def config_pyproject_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Add --pyproject to generate config suitable for inclusion in pyproject.toml."""
    f = option_with_underscore_traps(
        CliOpt.CONFIG_FOR_PYPROJECT,
        ArgKey.CONFIG_FOR_PYPROJECT,
        is_flag=True,
        help="Generate config for inclusion in pyproject.toml.",
    )(f)

    return f


def config_root_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Add --root to mark generated config as a discovery root."""
    f = option_with_underscore_traps(
        CliOpt.CONFIG_ROOT,
        ArgKey.CONFIG_ROOT,
        is_flag=True,
        help="Set generated config as root.",
    )(f)

    return f


def common_config_resolution_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common config resolution options to a Click command.

    Adds ``--no-config`` and ``--config/-c`` options.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.NO_CONFIG,
        ArgKey.NO_CONFIG,
        is_flag=True,
        help="Ignore local project config files (only use defaults).",
    )(f)

    f = option_with_underscore_traps(
        CliOpt.CONFIG_FILES,
        ArgKey.CONFIG_FILES,
        multiple=True,
        metavar="FILE",
        type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
        help="Additional config file(s) to load and merge.",
    )(f)

    return f


def config_dump_provenance_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply config layered dump options.

    Adds ``--show-layers``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.SHOW_CONFIG_LAYERS,
        ArgKey.SHOW_CONFIG_LAYERS,
        is_flag=True,
        default=False,
        help="Show layered TOML provenance followed by the final flattened config.",
    )(f)

    return f


def common_header_formatting_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common header formatting options.

    Adds ``--align-fields/--no-align-fields`` and ``--relative-to``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        f"{CliOpt.ALIGN_FIELDS}/{CliOpt.NO_ALIGN_FIELDS}",
        ArgKey.ALIGN_FIELDS,
        is_flag=True,
        default=None,
        help="Override whether header fields are aligned with colons.",
    )(f)

    f = option_with_underscore_traps(
        CliOpt.RELATIVE_TO,
        ArgKey.RELATIVE_TO,
        help="Header metadata: compute `file_relpath` and `relpath` from this directory.",
    )(f)

    return f


def check_policy_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Attach check-only policy options.

    These options control header insertion/update behavior and are only
    meaningful for the `topmark check` pipeline.

    Exposed options:
        - `--header-mutation-mode`
        - `--allow-header-in-empty-files` / `--no-allow-header-in-empty-files`
        - `--empty-insert-mode`
        - `--render-empty-header-when-no-fields` /
          `--no-render-empty-header-when-no-fields`
        - `--allow-reflow` / `--no-allow-reflow`

    Args:
        f: Click command function to decorate.

    Returns:
        Decorated Click command function.
    """
    f = option_with_underscore_traps(
        f"{CliOpt.POLICY_ALLOW_REFLOW}/{CliOpt.POLICY_NO_ALLOW_REFLOW}",
        ArgKey.POLICY_ALLOW_REFLOW,
        is_flag=True,
        default=None,
        help=(
            "Override whether content reflow is allowed during header insertion or "
            "update in the check pipeline."
        ),
    )(f)
    f = option_with_underscore_traps(
        (
            f"{CliOpt.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS}/"
            f"{CliOpt.POLICY_NO_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS}"
        ),
        ArgKey.POLICY_RENDER_EMPTY_HEADER_WHEN_NO_FIELDS,
        is_flag=True,
        default=None,
        help=(
            "Override whether an empty header may be inserted when no fields are "
            "configured in the check pipeline."
        ),
    )(f)

    f = option_with_underscore_traps(
        CliOpt.POLICY_EMPTY_INSERT_MODE,
        ArgKey.POLICY_EMPTY_INSERT_MODE,
        type=EnumChoiceParam(
            EmptyInsertMode,
            case_sensitive=False,
            kebab_case=True,
        ),
        default=None,
        help=enum_value_help_text(
            EmptyInsertMode,
            prefix=(
                "Define which inputs count as empty for header insertion in the check pipeline."
            ),
            suffix="Overrides config policy for this run.",
        ),
    )(f)
    f = option_with_underscore_traps(
        (
            f"{CliOpt.POLICY_ALLOW_HEADER_IN_EMPTY_FILES}/"
            f"{CliOpt.POLICY_NO_ALLOW_HEADER_IN_EMPTY_FILES}"
        ),
        ArgKey.POLICY_ALLOW_HEADER_IN_EMPTY_FILES,
        is_flag=True,
        default=None,
        help=(
            "Override whether headers may be inserted into files considered empty "
            "by the effective empty insert mode in the check pipeline."
        ),
    )(f)
    f = option_with_underscore_traps(
        CliOpt.POLICY_HEADER_MUTATION_MODE,
        ArgKey.POLICY_HEADER_MUTATION_MODE,
        type=EnumChoiceParam(
            HeaderMutationMode,
            case_sensitive=False,
            kebab_case=True,
        ),
        default=None,
        help=enum_value_help_text(
            HeaderMutationMode,
            prefix="Control which files `topmark check` may mutate.",
            suffix="Overrides config policy for this run.",
        ),
    )(f)

    return f


def shared_policy_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Attach policy options shared by multiple pipeline commands.

    These options affect common pipeline behavior such as file-type resolution
    and are meaningful for `topmark check`, `topmark strip`, and `topmark probe`.

    Exposed options:
        - `--allow-content-probe` / `--no-allow-content-probe`

    Args:
        f: Click command function to decorate.

    Returns:
        Decorated Click command function.
    """
    f = option_with_underscore_traps(
        f"{CliOpt.POLICY_ALLOW_CONTENT_PROBE}/{CliOpt.POLICY_NO_ALLOW_CONTENT_PROBE}",
        ArgKey.POLICY_ALLOW_CONTENT_PROBE,
        is_flag=True,
        default=None,
        help=(
            "Override whether file-type resolution may consult file contents when "
            "needed. Applies to check, strip, and probe."
        ),
    )(f)

    return f


def version_format_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply version formatting options.

    Adds ``--align-fields/--no-align-fields``,  ``--header-format`` and ``--relative-to``.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.SEMVER_VERSION,
        ArgKey.SEMVER_VERSION,
        is_flag=True,
        default=False,
        help="Render the version as SemVer instead of PEP 440 (maps rc→-rc.N, dev→-dev.N).",
    )(f)

    return f
