# topmark:header:start
#
#   project      : TopMark
#   file         : utils.py
#   file_relpath : src/topmark/cli/utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI rendering and machine-output helpers for TopMark.

This module contains helpers used by concrete CLI commands to render both
human-readable and machine-readable output:

- Human output:
  - summary and per-file guidance lines,
  - unified diffs,
  - TOML blocks (for config commands),
  - initial banners.

- Machine output:
  - emitters that write JSON and NDJSON payloads for config snapshots
    and processing results, using structures built in
    [`topmark.cli_shared.machine_output`][topmark.cli_shared.machine_output].

All printing goes through `ConsoleLike` instances obtained via
[`topmark.cli.console_helpers.get_console_safely`][topmark.cli.console_helpers.get_console_safely].
Data-shaping helpers (e.g. `build_config_payload`, `build_processing_results_payload`) live in
[`topmark.cli_shared.machine_output`][topmark.cli_shared.machine_output]
to keep them Click-free and reusable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from topmark.api.view import collect_outcome_counts, format_summary
from topmark.cli.console_helpers import get_console_safely
from topmark.cli.keys import CliCmd
from topmark.cli_shared.console_api import ConsoleLike
from topmark.cli_shared.machine_output import (
    build_processing_results_payload,
)
from topmark.cli_shared.utils import OutputFormat
from topmark.config.logging import get_logger
from topmark.config.machine.payloads import build_config_diagnostics_payload, build_config_payload
from topmark.constants import TOML_BLOCK_END, TOML_BLOCK_START
from topmark.core.machine.emitters import iter_ndjson_strings, serialize_json_envelope
from topmark.core.machine.formats import (
    MachineKey,
    MachineKind,
    MetaPayload,
    build_meta_payload,
    build_ndjson_record,
)
from topmark.pipeline.hints import Cluster
from topmark.utils.diff import render_patch

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    import click

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.logging import TopmarkLogger
    from topmark.config.machine.schemas import (
        ConfigDiagnosticCounts,
        ConfigDiagnosticEntry,
        ConfigDiagnosticsPayload,
        ConfigPayload,
    )
    from topmark.config.model import Config
    from topmark.pipeline.context.model import ProcessingContext
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
        console.print(format_summary(r))
        msg: str | None = make_message(r, apply_changes)
        if msg:
            console.print(console.styled(f"   {msg}", fg="yellow"))

        verbosity: int = r.config.verbosity_level or 0

        if verbosity > 0 and r.diagnostic_hints:
            console.print(
                console.styled(
                    "  Hints (newest first):",
                    fg="white",
                    italic=True,
                    bold=True,
                )
            )
            for h in reversed(r.diagnostic_hints.items):
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


def ensure_machine_format(fmt: OutputFormat) -> None:
    """Ensure the OutputFormat represents a machine format.

    Args:
        fmt (OutputFormat): the output format to be checked.

    Raises:
        ValueError: if the format provided is not a machine format.
    """
    if fmt not in {OutputFormat.JSON, OutputFormat.NDJSON}:
        raise ValueError(f"Unsupported machine output format: {fmt!r}")


def emit_config_machine(config: Config, *, fmt: OutputFormat) -> None:
    """Emit the effective Config snapshot in a machine-readable format.

    Shapes:
        - JSON: a single object matching ConfigPayload, wrapped as
          {"meta": ..., "config": ...}.
        - NDJSON: a single line of the form
          {"kind": "config", "meta": ..., "config": <ConfigPayload>}.

    Args:
        config (Config): Immutable runtime configuration to serialize.
        fmt (OutputFormat): Target machine format (JSON or NDJSON).
    """
    ensure_machine_format(fmt)

    console: ConsoleLike = get_console_safely()
    meta: MetaPayload = build_meta_payload()
    payload: ConfigPayload = build_config_payload(config)
    if fmt == OutputFormat.JSON:
        console.print(
            serialize_json_envelope(meta=meta, config=payload),
        )
    elif fmt == OutputFormat.NDJSON:
        record: dict[str, object] = build_ndjson_record(
            kind=MachineKind.CONFIG,
            meta=meta,
            payload=payload,
        )
        for line in iter_ndjson_strings([record]):
            console.print(line)


def emit_config_diagnostics_machine(config: Config, *, fmt: OutputFormat) -> None:
    """Emit Config diagnostics in a machine-readable format.

    Shapes:
        - JSON: a single object matching ConfigDiagnosticsPayload, wrapped as
          {"meta": ..., "config_diagnostics": ...}.
        - NDJSON: a single line of the form
          {"kind": "config_diagnostics", "meta": ..., \
            "config_diagnostics": <ConfigDiagnosticsPayload>}.

    Args:
        config (Config): Immutable runtime configuration providing diagnostics.
        fmt (OutputFormat): Target machine format (JSON or NDJSON).
    """
    ensure_machine_format(fmt)

    console: ConsoleLike = get_console_safely()
    meta: MetaPayload = build_meta_payload()
    payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    if fmt == OutputFormat.JSON:
        console.print(
            serialize_json_envelope(meta=meta, config_diagnostics=payload),
        )
        return
    elif fmt == OutputFormat.NDJSON:
        # NDJSON counts-only + streamed diagnostics
        diagnostics: list[ConfigDiagnosticEntry] = payload.diagnostics
        counts: ConfigDiagnosticCounts = payload.diagnostic_counts

        def records() -> Iterable[dict[str, object]]:
            yield build_ndjson_record(
                kind=MachineKind.CONFIG_DIAGNOSTICS,
                meta=meta,
                payload={
                    MachineKey.DIAGNOSTIC_COUNTS: counts.to_dict(),
                },
            )
            for d in diagnostics:
                yield build_ndjson_record(
                    kind=MachineKind.DIAGNOSTIC,
                    meta=meta,
                    payload={
                        MachineKey.DOMAIN: "config",
                        MachineKey.LEVEL: d.level,
                        MachineKey.MESSAGE: d.message,
                    },
                )

        for line in iter_ndjson_strings(records()):
            console.print(line)
        return


def emit_config_check_machine(
    config: Config,
    *,
    strict: bool,
    ok: bool,
    fmt: OutputFormat,
) -> None:
    """Emit `topmark config check` results in a machine-readable format.

    JSON:
      - One envelope: meta, config, config_diagnostics (full), summary.

    NDJSON (Pattern A + Pattern B):
      1) config
      2) config_diagnostics (counts-only)
      3) summary (command=config, subcommand=check)
      4+) diagnostic (domain=config) one per diagnostic
    """
    ensure_machine_format(fmt)

    console: ConsoleLike = get_console_safely()
    meta: MetaPayload = build_meta_payload()

    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)

    if fmt == OutputFormat.JSON:
        cfg_payload: ConfigPayload = build_config_payload(config)

        # Reuse counts from the diagnostics payload
        counts_only: ConfigDiagnosticCounts = cfg_diag_payload.diagnostic_counts

        summary: dict[str, object] = {
            MachineKey.COMMAND: CliCmd.CONFIG,
            MachineKey.SUBCOMMAND: CliCmd.CONFIG_CHECK,
            MachineKey.OK: ok,
            MachineKey.STRICT: strict,
            MachineKey.DIAGNOSTIC_COUNTS: counts_only.to_dict(),
            MachineKey.CONFIG_FILES: [str(p) for p in config.config_files],
        }

        console.print(
            serialize_json_envelope(
                meta=meta,
                config=cfg_payload,
                config_diagnostics=cfg_diag_payload,
                summary=summary,
            )
        )
        return

    elif fmt == OutputFormat.NDJSON:
        # Reuse existing emitters for shared records
        emit_config_machine(config, fmt=OutputFormat.NDJSON)

        # Config diagnostics stats (counts per severity level)
        # Reuse counts from the diagnostics payload
        counts_only: ConfigDiagnosticCounts = cfg_diag_payload.diagnostic_counts

        summary: dict[str, object] = {
            MachineKey.COMMAND: CliCmd.CONFIG,
            MachineKey.SUBCOMMAND: CliCmd.CONFIG_CHECK,
            MachineKey.OK: ok,
            MachineKey.STRICT: strict,
            MachineKey.DIAGNOSTIC_COUNTS: counts_only.to_dict(),
            MachineKey.CONFIG_FILES: [str(p) for p in config.config_files],
        }

        def records() -> Iterable[dict[str, object]]:
            # Config check summary
            yield build_ndjson_record(
                kind=MachineKind.CONFIG_DIAGNOSTICS,
                meta=meta,
                payload={MachineKey.DIAGNOSTIC_COUNTS: counts_only.to_dict()},
            )
            yield build_ndjson_record(
                kind=MachineKind.SUMMARY,
                meta=meta,
                payload=summary,
            )

            # One diagnostic per line
            for d in config.diagnostics:
                yield build_ndjson_record(
                    kind=MachineKind.DIAGNOSTIC,
                    meta=meta,
                    payload={
                        MachineKey.DOMAIN: "config",
                        MachineKey.LEVEL: d.level.value,
                        MachineKey.MESSAGE: d.message,
                    },
                )

        for line in iter_ndjson_strings(records()):
            console.print(line)


def render_config_check_markdown(
    *,
    ok: bool,
    strict: bool,
    counts: ConfigDiagnosticCounts,
    diagnostics: list[ConfigDiagnosticEntry],
    config_files: list[str],
    verbosity_level: int,
) -> str:
    """Render `topmark config check` output as Markdown."""
    lines: list[str] = []
    lines.append("## topmark config check\n")
    status = "OK" if ok else "FAILED"

    # Summary
    lines.append("### Summary\n")
    lines.append(f"- **Status:** {status}")
    lines.append(f"- **Strict:** {str(strict).lower()}")
    lines.append(f"- **Errors:** {counts.error}")
    lines.append(f"- **Warnings:** {counts.warning}\n")

    # Diagnostics
    if diagnostics:
        lines.append("### Diagnostics\n")
        for d in diagnostics:
            lines.append(f"- **{d.level}**: {d.message}")
        lines.append("")

    # Config files
    if verbosity_level > 0:
        lines.append(f"### Config files processed ({len(config_files)})\n")
        for i, p in enumerate(config_files, start=1):
            lines.append(f"{i}. {p}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_toml_block(
    *,
    console: ConsoleLike,
    title: str,
    toml_text: str,
    verbosity_level: int,
) -> None:
    """Render a TOML snippet with optional banner and BEGIN/END markers.

    This is used by commands like `topmark config dump`,
    `topmark config defaults`, and `topmark config init` in the default
    (human) output format.

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
            "meta": ...,
            "config": <ConfigPayload>,
            "config_diagnostics": <ConfigDiagnosticsPayload>,
            "results": [ <per-file result dict> ... ]
          }

        - summary mode (summary_mode=True):
          {
            "meta": ...,
            "config": <ConfigPayload>,
            "config_diagnostics": <ConfigDiagnosticsPayload>,
            "summary": {
              "<outcome>": { "count": int, "label": str },
              ...
            }
          }

    NDJSON shapes:
        - First line:  {"kind": "config", "meta": ..., "config": <ConfigPayload>}
        - Second line: {"kind": "config_diagnostics",
                        "config_diagnostics": <ConfigDiagnosticsPayload>}
        - Remaining lines:
            * detail mode: {"kind": "result", ...}
            * summary mode: {"kind": "summary", "summary": { ... } }

    Notes:
        - This function never prints ANSI color or diffs.
        - Diffs (`--diff`) are strictly human-only.
    """
    ensure_machine_format(fmt)

    console: ConsoleLike = get_console_safely()

    meta: MetaPayload = build_meta_payload()

    # Prepare schema pieces once (display Config diagnostics when processing files)
    cfg_payload: ConfigPayload = build_config_payload(config)
    cfg_diag_payload: ConfigDiagnosticsPayload = build_config_diagnostics_payload(config)
    results_payload: dict[str, Any] = build_processing_results_payload(
        results,
        summary_mode=summary_mode,
    )

    if fmt == OutputFormat.JSON:
        # Envelope: meta + config + config diagnostics + results
        # OR meta + config + config diagnostics + summary
        # results_payload is {"results": [...]} or {"summary": {...}}
        console.print(
            serialize_json_envelope(
                meta=meta,
                config=cfg_payload,
                config_diagnostics=cfg_diag_payload,
                **results_payload,
            ),
        )

    elif fmt == OutputFormat.NDJSON:
        # First: config metadata record (excluding diagnostics and counts)
        counts_only: ConfigDiagnosticCounts = cfg_diag_payload.diagnostic_counts

        def records() -> Iterable[dict[str, object]]:
            # Config record
            yield build_ndjson_record(
                kind=MachineKind.CONFIG,
                meta=meta,
                payload=cfg_payload,
            )
            # Config diagnostics counts-only
            yield build_ndjson_record(
                kind=MachineKind.CONFIG_DIAGNOSTICS,
                meta=meta,
                payload={
                    MachineKey.DIAGNOSTIC_COUNTS: counts_only.to_dict(),
                },
            )
            # One diagnostic per line
            for d in config.diagnostics:
                yield build_ndjson_record(
                    kind=MachineKind.DIAGNOSTIC,
                    meta=meta,
                    payload={
                        MachineKey.DOMAIN: "config",
                        MachineKey.LEVEL: d.level.value,
                        MachineKey.MESSAGE: d.message,
                    },
                )
            if summary_mode:
                counts = collect_outcome_counts(results)
                for key, (n, label, _color) in counts.items():
                    yield build_ndjson_record(
                        kind=MachineKind.SUMMARY,
                        meta=meta,
                        payload={
                            "key": key,
                            "count": n,
                            "label": label,
                        },
                    )
            else:
                for r in results:
                    yield build_ndjson_record(
                        kind=MachineKind.RESULT,
                        meta=meta,
                        payload=r.to_dict(),
                    )

        for line in iter_ndjson_strings(records()):
            console.print(line)


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
