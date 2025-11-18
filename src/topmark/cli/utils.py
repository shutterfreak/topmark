# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/cli/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI utility helpers for TopMark.

This module provides utility functions shared across CLI commands, including
header defaults extraction, color handling, and summary rendering.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Sequence, TypedDict, cast

from topmark.api.view import collect_outcome_counts
from topmark.cli.console_helpers import get_console_safely
from topmark.cli_shared.console_api import ConsoleLike
from topmark.cli_shared.utils import OutputFormat
from topmark.config.logging import get_logger
from topmark.constants import TOML_BLOCK_END, TOML_BLOCK_START
from topmark.core.diagnostics import DiagnosticStats, compute_diagnostic_stats
from topmark.pipeline.hints import Cluster
from topmark.utils.diff import render_patch

if TYPE_CHECKING:
    from collections.abc import Callable

    import click

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.io import TomlTable
    from topmark.config.logging import TopmarkLogger
    from topmark.config.model import Config
    from topmark.pipeline.context import ProcessingContext
    from topmark.pipeline.views import DiffView, UpdatedView


logger: TopmarkLogger = get_logger(__name__)


def render_summary_counts(view_results: list[ProcessingContext], *, total: int) -> None:
    """Print the human summary (aligned counts by outcome)."""
    console: ConsoleLike = get_console_safely()
    console.print()
    console.print(console.styled("Summary by outcome:", bold=True, underline=True))

    counts: dict[str, tuple[int, str, Callable[[str], str]]] = collect_outcome_counts(view_results)
    label_width: int = max((len(v[1]) for v in counts.values()), default=0) + 1
    num_width: int = len(str(total))
    for _key, (n, label, color) in counts.items():
        console.print(color(f"  {label:<{label_width}}: {n:>{num_width}}"))


def render_per_file_guidance(
    view_results: list[ProcessingContext],
    *,
    make_message: Callable[[ProcessingContext, bool], str | None],
    apply_changes: bool,
) -> None:
    """Echo one human guidance line per result (when not in --summary)."""
    console: ConsoleLike = get_console_safely()
    for r in view_results:
        console.print(r.summary)
        msg: str | None = make_message(r, apply_changes)
        if msg:
            console.print(console.styled(f"   {msg}", fg="yellow"))

        verbosity: int = r.config.verbosity_level or 0

        if verbosity > 0 and r.reason_hints:
            console.print(
                console.styled(
                    "  Hints (newest first):",
                    fg="white",
                    italic=True,
                    bold=True,
                )
            )
            for h in reversed(r.reason_hints):
                if h.cluster == Cluster.UNCHANGED.value:
                    color: str = "green"
                elif h.cluster in {Cluster.CHANGED.value, Cluster.WOULD_CHANGE.value}:
                    color = "bright_yellow"
                elif h.cluster in {Cluster.BLOCKED_POLICY.value, Cluster.SKIPPED.value}:
                    color = "bright_blue"
                elif h.cluster == Cluster.ERROR.value:
                    color = "bright_red"
                else:
                    color = "white"

                # Summary line
                summary: str = (
                    f"     {h.axis.value:10s}: {h.cluster:10s} - {h.code:16s}: "
                    f"{h.message}{' (terminal)' if h.terminal else ''}"
                )
                console.print(
                    console.styled(
                        summary,
                        fg=color,
                        italic=True,
                    )
                )

                # Optional detail vs "use -vv" nudge
                if h.detail:
                    if verbosity > 1:
                        for line in h.detail.splitlines():
                            console.print(
                                console.styled(
                                    f"         {line}",
                                    fg=color,
                                    italic=True,
                                )
                            )
                    else:
                        console.print(
                            console.styled(
                                "         (use -vv to display detailed diagnostics)",
                                fg="white",
                                italic=True,
                            )
                        )


def emit_diffs(results: list[ProcessingContext], *, diff: bool, command: click.Command) -> None:
    """Print unified diffs for changed files in human output mode.

    Args:
      results (list[ProcessingContext]): List of processing contexts to inspect.
      diff (bool): If True, print unified diffs; if False, do nothing.
      command (click.Command): The Click command object (used for structured logging).

    Notes:
      - Diffs are only printed in human (DEFAULT) output mode.
      - Files with no changes do not emit a diff.
    """
    console: ConsoleLike = get_console_safely()
    for r in results:
        if diff:
            diff_view: DiffView | None = r.views.diff
            diff_text: str | None = diff_view.text if diff_view else None
            if diff_text:
                console.print(render_patch(diff_text))


class ConfigDiagnosticEntry(TypedDict):
    """Machine-readable diagnostic entry for config metadata."""

    level: str
    message: str


class ConfigDiagnosticCounts(TypedDict):
    """Aggregated per-level counts for config diagnostics."""

    info: int
    warning: int
    error: int


class ConfigPayload(TypedDict, total=False):
    """JSON-friendly representation of the effective TopMark configuration.

    The shape loosely mirrors ``Config.to_toml_dict(include_files=False)`` but
    guarantees JSON-serializable values (paths/Enums normalized to strings).

    Diagnostics are emitted separately via ConfigDiagnosticsPayload.
    """

    # loosely mirrors to_toml_dict structure with JSON-friendly types
    fields: dict[str, str]
    header: dict[str, list[str]]
    formatting: dict[str, Any]
    writer: dict[str, Any]
    files: dict[str, Any]
    policy: dict[str, Any]
    policy_by_type: dict[str, Any]


def _jsonify_config_value(value: Any) -> Any:
    """Recursively convert config payload values into JSON-serializable forms.

    This helper normalizes:
      - pathlib.Path -> str
      - Enum -> Enum.name
      - Mapping -> dict with JSON-serializable values
      - list/tuple/set/frozenset -> list with JSON-serializable values

    It is intentionally conservative and only applies to the config payload
    to avoid surprising transformations elsewhere.
    """
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, Mapping):
        # Safe: `value` is a Mapping after the isinstance check; we treat keys
        # as generic objects and values as Any for JSONification purposes.
        mapping: Mapping[object, Any] = cast("Mapping[object, Any]", value)
        return {str(k): _jsonify_config_value(v) for k, v in mapping.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        # Safe: `value` is a collection after the isinstance check; iterate as objects.
        seq: Iterable[object] = cast("Iterable[object]", value)
        return [_jsonify_config_value(v) for v in seq]
    return value


def build_config_payload(config: Config) -> ConfigPayload:
    """Build a JSON-friendly payload capturing a Config snapshot.

    Args:
        config (Config): Immutable runtime configuration instance.

    Returns:
        ConfigPayload: JSON-serializable representation of the Config, without
            diagnostics.
    """
    base: TomlTable = config.to_toml_dict(include_files=False)  # TomlTable ~ dict[str, Any]

    writer = base.get("writer", {})
    # Make sure Enums become simple strings
    target = config.output_target.name if config.output_target is not None else None
    strategy = config.file_write_strategy.name if config.file_write_strategy is not None else None
    writer = {**writer, "target": target, "strategy": strategy}
    base["writer"] = writer

    json_safe_base: Any = _jsonify_config_value(base)
    return json_safe_base  # type: ignore[return-value]


class ConfigDiagnosticsPayload(TypedDict, total=False):
    """Machine-readable diagnostics collected while building the Config.

    Structure:
      - diagnostics: list of {level, message} entries.
      - diagnostic_counts: aggregate per-level counts.
    """

    diagnostics: list[ConfigDiagnosticEntry]
    diagnostic_counts: ConfigDiagnosticCounts


def build_config_diagnostics_payload(config: Config) -> ConfigDiagnosticsPayload:
    """Build a JSON-friendly diagnostics payload for a given Config.

    Args:
        config (Config): The Config instance.

    Returns:
        ConfigDiagnosticsPayload: JSON-serializable diagnostics metadata for
            the given Config.
    """
    diag: ConfigDiagnosticsPayload = {}
    diag_entries: list[ConfigDiagnosticEntry] = [
        {"level": d.level.value, "message": d.message} for d in config.diagnostics
    ]
    stats: DiagnosticStats = compute_diagnostic_stats(config.diagnostics)
    diag_counts: ConfigDiagnosticCounts = {
        "info": stats.n_info,
        "warning": stats.n_warning,
        "error": stats.n_error,
    }

    diag["diagnostics"] = diag_entries
    diag["diagnostic_counts"] = diag_counts

    json_safe_diag: Any = _jsonify_config_value(diag)
    return json_safe_diag  # type: ignore[return-value]


def emit_config_machine(config: Config, *, fmt: OutputFormat) -> None:
    """Emit the effective Config snapshot in a machine-readable format.

    Shapes:
        - JSON: a single object matching ConfigPayload.
        - NDJSON: a single line of the form
          ``{"kind": "config", "config": <ConfigPayload>}``.

    Args:
        config (Config): Immutable runtime configuration to serialize.
        fmt (OutputFormat): Target machine format (JSON or NDJSON).
    """
    import json as _json

    console: ConsoleLike = get_console_safely()
    payload: ConfigPayload = build_config_payload(config)
    if fmt == OutputFormat.JSON:
        console.print(_json.dumps(payload, indent=2))
    elif fmt == OutputFormat.NDJSON:
        console.print(
            _json.dumps(
                {
                    "kind": "config",
                    "config": payload,
                }
            )
        )


def emit_config_diagnostics_machine(config: Config, *, fmt: OutputFormat) -> None:
    """Emit Config diagnostics in a machine-readable format.

    Shapes:
        - JSON: a single object matching ConfigDiagnosticsPayload.
        - NDJSON: a single line of the form
          ``{"kind": "config_diagnostics", "config_diagnostics": <ConfigDiagnosticsPayload>}``.

    Args:
        config (Config): Immutable runtime configuration providing diagnostics.
        fmt (OutputFormat): Target machine format (JSON or NDJSON).
    """
    import json as _json

    console: ConsoleLike = get_console_safely()
    payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)
    if fmt == OutputFormat.JSON:
        console.print(_json.dumps(payload, indent=2))
    elif fmt == OutputFormat.NDJSON:
        console.print(
            _json.dumps(
                {
                    "kind": "config_diagnostics",
                    "config_diagnostics": payload,
                },
            )
        )


def render_toml_block(
    *,
    console: ConsoleLike,
    title: str,
    toml_text: str,
    verbosity_level: int,
) -> None:
    """Render a TOML snippet with optional banner and BEGIN/END markers.

    This is used by commands like `dump-config` and `show-defaults` in the
    default (human) output format.

    Args:
        console (ConsoleLike): Console instance for printing styled output.
        title (str): Title line shown above the block when verbosity > 0.
        toml_text (str): The TOML content to render.
        verbosity_level (int): Effective verbosity; 0 disables banners.
    """
    if verbosity_level > 0:
        console.print(
            console.styled(
                title,
                bold=True,
                underline=True,
            )
        )
        console.print(
            console.styled(
                TOML_BLOCK_START,
                fg="cyan",
                dim=True,
            )
        )

    console.print(
        console.styled(
            toml_text,
            fg="cyan",
        )
    )

    if verbosity_level > 0:
        console.print(
            console.styled(
                TOML_BLOCK_END,
                fg="cyan",
                dim=True,
            )
        )


class ProcessingSummaryEntry(TypedDict):
    """Machine-readable summary entry for per-outcome counts."""

    count: int
    label: str


def build_processing_results_payload(
    results: list[ProcessingContext],
    *,
    summary_mode: bool,
) -> dict[str, Any]:
    """Build the machine-readable payload for processing results.

    For JSON:
      - summary_mode=False: this will be nested under "results".
      - summary_mode=True: this will be nested under "summary".
    """
    if summary_mode:
        counts = collect_outcome_counts(results)
        summary: dict[str, ProcessingSummaryEntry] = {
            key: {"count": cnt, "label": label} for key, (cnt, label, _color) in counts.items()
        }
        return {"summary": summary}
    else:
        details: list[dict[str, object]] = [r.to_dict() for r in results]
        return {"results": details}


def emit_processing_results_machine(
    config: Config,
    results: list[ProcessingContext],
    fmt: OutputFormat,
    summary_mode: bool,
) -> None:
    """Emit processing results in JSON/NDJSON format for machine consumption.

    Args:
      config (Config): The Config instance.
      results (list[ProcessingContext]): Ordered list of per-file processing results.
      fmt (OutputFormat): Output format (`OutputFormat.JSON` or `OutputFormat.NDJSON`).
      summary_mode (bool): If True, emit aggregated counts instead of per-file entries.

    JSON shapes:
        - detail mode (summary_mode=False):
          {
            "config": <ConfigPayload>,
            "config_diagnostics": <ConfigDiagnosticsPayload>,
            "results": [ <per-file result dict> ... ]
          }

        - summary mode (summary_mode=True):
          {
            "config": <ConfigPayload>,
            "config_diagnostics": <ConfigDiagnosticsPayload>,
            "summary": {
              "<outcome>": { "count": int, "label": str },
              ...
            }
          }

    NDJSON shapes:
        - First line:  {"kind": "config", "config": <ConfigPayload>}
        - Second line: {"kind": "config_diagnostics",
                        "config_diagnostics": <ConfigDiagnosticsPayload>}
        - Remaining lines:
            * detail mode: {"kind": "result", ...}
            * summary mode: {"kind": "summary", "summary": { ... } }

    Notes:
        - This function never prints ANSI color or diffs.
        - Diffs (`--diff`) are strictly human-only.
    """
    import json as _json

    console: ConsoleLike = get_console_safely()

    # Prepare schema pieces once (display Config diagnostics when processing files)
    cfg_payload: ConfigPayload = build_config_payload(config)
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)
    results_payload: dict[str, Any] = build_processing_results_payload(
        results,
        summary_mode=summary_mode,
    )

    if fmt == OutputFormat.JSON:
        # Envelope: config + config diagnostics + results OR config + config diagnostics + summary
        # results_payload is {"results": [...]} or {"summary": {...}}
        envelope: dict[str, object] = {
            "config": cfg_payload,
            "config_diagnostics": cfg_diag_payload,
        }
        envelope.update(results_payload)
        console.print(_json.dumps(envelope, indent=2))

    elif fmt == OutputFormat.NDJSON:
        # First: config metadata record (excluding diagnostics and counts)
        console.print(
            _json.dumps(
                {
                    "kind": "config",
                    "config": cfg_payload,
                }
            )
        )
        # Second: config diagnostics diagnostics and counts:
        console.print(
            _json.dumps(
                {
                    "kind": "config_diagnostics",
                    "config_diagnostics": cfg_diag_payload,
                }
            )
        )

        if summary_mode:
            counts = collect_outcome_counts(results)
            for key, (n, label, _color) in counts.items():
                console.print(
                    _json.dumps(
                        {
                            "kind": "summary",
                            "key": key,
                            "count": n,
                            "label": label,
                        }
                    )
                )
        else:
            for r in results:
                console.print(
                    _json.dumps(
                        {
                            "kind": "result",
                            **r.to_dict(),
                        }
                    )
                )


def emit_updated_content_to_stdout(results: list[ProcessingContext]) -> None:
    """Write updated content to stdout when applying to a single STDIN file."""
    console: ConsoleLike = get_console_safely()
    for r in results:
        updated_view: UpdatedView | None = r.views.updated
        if updated_view:
            updated_file_lines: Sequence[str] | Iterable[str] | None = updated_view.lines
            if updated_file_lines is not None:
                console.print("".join(updated_file_lines), nl=False)


def render_banner(ctx: click.Context, *, n_files: int) -> None:
    """Render the initial banner for a command.

    Args:
      ctx (click.Context): Click context (used to get the command name).
      n_files (int): Number of files to be processed.
    """
    console: ConsoleLike = get_console_safely()
    console.print(console.styled(f"\n🔍 Processing {n_files} file(s):\n", fg="blue"))
    console.print(
        console.styled(f"📋 TopMark {ctx.command.name} Results:", bold=True, underline=True)
    )
