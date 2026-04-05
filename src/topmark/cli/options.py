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
    help: NotRequired[str | None]
    metavar: NotRequired[str | None]
    type: NotRequired[click.ParamType | type | object]
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
) -> tuple[list[str], list[str], list[str]]:
    """Remove '-' sentinels so downstream code never treats STDIN as a file path.

    Args:
        files_from: Values passed via `--files-from`.
        include_from: Values passed via `--include-from`.
        exclude_from: Values passed via `--exclude-from`.

    Returns:
        A triple of lists with '-' removed from each.
    """
    return (
        [x for x in files_from if x != "-"],
        [x for x in include_from if x != "-"],
        [x for x in exclude_from if x != "-"],
    )


def extract_stdin_for_from_options(
    files_from: Iterable[str],
    include_from: Iterable[str],
    exclude_from: Iterable[str],
    stdin_text: str | None = None,
) -> tuple[str | None, str | None, str | None]:
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
        `(files_from_stdin, include_from_stdin, exclude_from_stdin)` where only
        one entry is non-None.

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

    return text_files, text_includes, text_excludes


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


def resolve_verbosity(verbose_count: int, quiet_count: int) -> int:
    """Resolve an integer verbosity level from -v/-q counts.

    Args:
        verbose_count: Number of times `-v/--verbose` is passed.
        quiet_count: Number of times `-q/--quiet` is passed.

    Returns:
        Signed verbosity level (`verbose_count - quiet_count`).
    """
    verbosity_level: int = verbose_count - quiet_count
    return verbosity_level


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
    raise click.UsageError(f"Unknown option: {bad}. Did you mean {suggestion}?")


def trap_underscored_spellings(*names: str) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Register hidden underscored spellings that raise a helpful error.

    This wraps `click.option` with common settings for underscored
    long-option traps, so callers don't repeat the same boilerplate.

    It also assigns a **unique destination name** for the hidden option so
    Click's parameter source tracking does not overlap with the real option's
    destination (e.g., ``exclude_from``). Without this, the trap callback can
    incorrectly detect COMMANDLINE source when the *hyphenated* option was
    used, leading to false positives.

    Args:
        *names: One or more underscored long option spellings to trap,
            e.g. "--exclude_from". Multiple spellings are supported so a
            single decorator can catch several spellings.

    Returns:
        A Click option decorator compatible with stacking.

    Raises:
        ValueError: If no names were provided.
    """
    if not names:
        raise ValueError("trap_underscored_spellings requires at least one option name")

    first: str = names[0]
    # Create a unique, non-conflicting Python destination name for the hidden option
    dest: str = f"_trap__{first.lstrip('-').replace('-', '_')}"
    return click.option(
        *names,
        dest,
        hidden=True,
        expose_value=False,
        is_eager=True,
        multiple=True,
        callback=_trap_underscored_option,
    )


def option_with_underscore_traps(
    *param_decls: str,
    **attrs: Unpack[_ClickOptionKwargs],
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Like `click.option`, but also traps underscored spellings.

    For each canonical long option declaration of the form `--foo-bar`, this helper
    also registers a hidden eager option `--foo_bar` that raises a helpful error
    suggesting the hyphenated spelling.

    This is Pattern B: the trap is attached alongside the real option so call sites
    don't need to remember to register traps separately.

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
        and ("/" not in d)  # Keep paired flags: don’t generate underscore traps for them
        and ("_" not in d)
        and ("-" in d[2:])
    ]
    trap_longs: list[str] = ["--" + d[2:].replace("-", "_") for d in canonical_longs]

    real_decorator = click.option(*param_decls, **attrs)

    if not trap_longs:
        return real_decorator

    # Deterministic hidden destination; avoid collisions with real dest names.
    key: str = canonical_longs[0][2:].replace("-", "_")
    trap_dest: str = f"_trap__{key}"

    trap_decorator = click.option(
        *trap_longs,
        trap_dest,
        hidden=True,
        expose_value=False,
        is_eager=True,
        multiple=True,
        callback=_trap_underscored_option,
    )

    def decorator(f: Callable[_P, _R]) -> Callable[_P, _R]:
        f = trap_decorator(f)
        f = real_decorator(f)
        return f

    return decorator


# ---- Option decorators ----


def common_verbose_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Adds --verbose and --quiet options to a command.

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function with verbosity options added.

    Behavior:
        Adds -v/--verbose and -q/--quiet options that count occurrences.
        These options are mutually exclusive and control human-facing output verbosity.
    """
    f = option_with_underscore_traps(
        CliOpt.VERBOSE,
        ArgKey.VERBOSE,
        CliShortOpt.VERBOSE,
        count=True,
        help="Increase verbosity. Specify up to twice for more detail.",
    )(f)
    f = option_with_underscore_traps(
        CliOpt.QUIET,
        ArgKey.QUIET,
        CliShortOpt.QUIET,
        count=True,
        help="Suppress output. Specify up to twice for even less.",
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
        type=click.Choice([m.value for m in ColorMode]),
        default=None,
        help="Color output: auto (default), always, or never.",
    )(f)
    f = option_with_underscore_traps(
        CliOpt.NO_COLOR_MODE,
        ArgKey.NO_COLOR_MODE,
        is_flag=True,
        help=f"Disable color output (equivalent to {CliOpt.COLOR_MODE} never).",
    )(f)
    return f


def common_ui_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Convenience decorator (verbosity + color mode).

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function with verbosity and color options added.

    Behavior:
        Adds --verbose and --quiet options (mutually exclusive).
        Adds --color with choices (auto, always, never).
        Adds --no-color flag that disables color output.
    """
    f = common_verbose_options(f)
    f = common_color_options(f)
    return f


def common_output_format_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common output format options.

    Adds the ``--output-format`` option which accepts OutputFormat values for human use (``text``,
    ``markdown``) and machine formats (``json``, ``ndjson``). If not set, it will be resolved to
    ``text`` (ANSI-capable).

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
        help=f"Output format ({', '.join(v.value for v in OutputFormat)}).",
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


def common_from_sources_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Apply common file selection and filtering options.

    Adds the following file source options: ``--files-from``, ``--include-from``,
    ``--exclude-from``.

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

    Args:
        f: The Click command function to decorate.

    Returns:
        The decorated function.
    """
    f = option_with_underscore_traps(
        CliOpt.INCLUDE_FILE_TYPES,
        CliOpt.INCLUDE_FILE_TYPE,
        CliShortOpt.INCLUDE_FILE_TYPES,
        ArgKey.INCLUDE_FILE_TYPES,
        multiple=True,
        callback=_split_csv_multi_option,
        help=(
            "Filter: restrict to given file types. Preferred spelling is "
            f"{CliOpt.INCLUDE_FILE_TYPES} (alias: {CliOpt.INCLUDE_FILE_TYPE}). "
            "Applied after path include/exclude filtering. "
            "May be repeated and/or given as a comma-separated list."
        ),
    )(f)

    f = option_with_underscore_traps(
        CliOpt.EXCLUDE_FILE_TYPES,
        CliOpt.EXCLUDE_FILE_TYPE,
        CliShortOpt.EXCLUDE_FILE_TYPES,
        ArgKey.EXCLUDE_FILE_TYPES,
        multiple=True,
        callback=_split_csv_multi_option,
        help=(
            "Filter: exclude given file types. Preferred spelling is "
            f"{CliOpt.EXCLUDE_FILE_TYPES} (alias: {CliOpt.EXCLUDE_FILE_TYPE}). "
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
        ArgKey.REPORT,
        type=EnumChoiceParam(
            ReportScope,
            case_sensitive=False,
            kebab_case=True,
        ),
        default=ReportScope.ACTIONABLE,
        show_default=True,
        help=(
            "Reporting scope for human per-file output: "
            "'actionable': list would-change results and other attention-worthy states; "
            "summarize unsupported entries separately. "
            "'noncompliant': list actionable results plus unsupported entries. "
            "'all': list every processed result, including unchanged entries. "
            "Ignored for summary mode and machine-readable formats."
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


def config_strict_checking_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Add strict config checking option (treat warnings as failures).

    Use `--strict` to force strict checking, `--no-strict` to disable it,
    and omit the flag altogether to defer to TOML-defined strictness.
    """
    f = option_with_underscore_traps(
        f"{CliOpt.STRICT_CONFIG_CHECKING}/{CliOpt.NO_STRICT_CONFIG_CHECKING}",
        ArgKey.STRICT_CONFIG_CHECKING,
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
    f = click.option(
        CliOpt.POLICY_EMPTY_INSERT_MODE,
        ArgKey.POLICY_EMPTY_INSERT_MODE,
        type=EnumChoiceParam(
            EmptyInsertMode,
            case_sensitive=False,
            kebab_case=True,
        ),
        default=None,
        help=(
            "Define which inputs count as empty for header insertion in the check "
            "pipeline: bytes-empty, logical-empty, or whitespace-empty. "
            "Overrides config policy for this run."
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
    f = click.option(
        CliOpt.POLICY_HEADER_MUTATION_MODE,
        ArgKey.POLICY_HEADER_MUTATION_MODE,
        type=EnumChoiceParam(
            HeaderMutationMode,
            case_sensitive=False,
            kebab_case=True,
        ),
        default=None,
        help=(
            "Control which files `topmark check` may mutate: all, add-only, or "
            "update-only. Overrides config policy for this run."
        ),
    )(f)

    return f


def shared_policy_options(f: Callable[_P, _R]) -> Callable[_P, _R]:
    """Attach policy options shared by multiple pipeline commands.

    These options affect common pipeline behavior such as file-type resolution
    and are meaningful for both `topmark check` and `topmark strip`.

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
            "Override whether file-type detection may consult file contents when "
            "needed. Applies to both check and strip."
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
