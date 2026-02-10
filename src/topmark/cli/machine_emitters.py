# topmark:header:start
#
#   project      : TopMark
#   file         : machine_emitters.py
#   file_relpath : src/topmark/cli/machine_emitters.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI helpers for emitting machine-readable output.

This module is Click/console-aware and is responsible only for writing already
rendered machine-output strings (JSON or NDJSON) to the active ConsoleLike.

All shaping and serialization lives in [`topmark.core.machine`][topmark.core.machine].
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.console_helpers import get_console_safely
from topmark.config.machine import (
    serialize_config,
    serialize_config_check,
    serialize_config_diagnostics,
)
from topmark.core.formats import (
    OutputFormat,
    is_machine_format,
)
from topmark.pipeline.machine import (
    serialize_processing_results,
)
from topmark.registry.machine import (
    serialize_filetypes,
    serialize_processors,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from topmark.cli_shared.console_api import ConsoleLike
    from topmark.config.model import Config
    from topmark.core.machine.schemas import MetaPayload
    from topmark.pipeline.context.model import ProcessingContext


def emit_machine(
    serialized: str | Iterable[str],
    *,
    nl: bool = True,
) -> None:
    """Emit the serialized machine format to the ConsoleLike.

    Args:
        serialized: The serialized machine data to emit.
        nl: If True (default), emit a newline at the end of each line,
    """
    if not serialized:
        # Nothing to print
        return

    console: ConsoleLike = get_console_safely()
    if isinstance(serialized, str):
        console.print(serialized, nl=nl)
    else:
        for line in serialized:
            console.print(line, nl=nl)


def emit_processing_results_machine(
    *,
    meta: MetaPayload,
    config: Config,
    results: list[ProcessingContext],
    fmt: OutputFormat,
    summary_mode: bool,
) -> None:
    """Emit already-rendered machine strings to console.

    Args:
        meta: The machine metadata payload.
        config: The Config instance.
        results: Ordered list of per-file processing results.
        fmt: Output format (`OutputFormat.JSON` or `OutputFormat.NDJSON`).
        summary_mode: If True, emit aggregated counts instead of per-file entries.

    Raises:
        ValueError: if `fmt` is not a machine format.
    """
    if not is_machine_format(fmt):
        raise ValueError(f"Unsupported machine output format: {fmt!r}")

    serialized: str | Iterator[str] = serialize_processing_results(
        meta=meta,
        config=config,
        results=results,
        fmt=fmt,
        summary_mode=summary_mode,
    )

    # Do not emit trailing newline for JSON
    nl: bool = fmt != OutputFormat.JSON
    emit_machine(serialized, nl=nl)


def emit_config_machine(
    *,
    meta: MetaPayload,
    config: Config,
    fmt: OutputFormat,
) -> None:
    """Emit the effective Config snapshot in a machine-readable format to ConsoleLike.

    Shapes:
        - JSON: a single object matching ConfigPayload, wrapped as
          {"meta": ..., "config": ...}.
        - NDJSON: a single line of the form
          {"kind": "config", "meta": ..., "config": <ConfigPayload>}.

    Args:
        meta: The machine metadata payload.
        config: Immutable runtime configuration to serialize.
        fmt: Target machine format (JSON or NDJSON).

    Raises:
        ValueError: if `fmt` is not a supported machine format.
    """
    if not is_machine_format(fmt):
        raise ValueError(f"Unsupported machine output format: {fmt!r}")

    serialized: str | Iterator[str] = serialize_config(
        meta=meta,
        config=config,
        fmt=fmt,
    )

    # Do not emit trailing newline for JSON
    nl: bool = fmt != OutputFormat.JSON
    emit_machine(serialized, nl=nl)


def emit_config_diagnostics_machine(
    *,
    meta: MetaPayload,
    config: Config,
    fmt: OutputFormat,
) -> None:
    """Emit Config diagnostics in a machine-readable format to ConsoleLike.

    Shapes:
        - JSON: a single object matching ConfigDiagnosticsPayload, wrapped as
          {"meta": ..., "config_diagnostics": ...}.
        - NDJSON: a single line of the form
          {"kind": "config_diagnostics", "meta": ..., \
            "config_diagnostics": <ConfigDiagnosticsPayload>}.

    Args:
        meta: The machine metadata payload.
        config: Immutable runtime configuration providing diagnostics.
        fmt: Target machine format (JSON or NDJSON).

    Raises:
        ValueError: if `fmt` is not a supported machine format.
    """
    if not is_machine_format(fmt):
        raise ValueError(f"Unsupported machine output format: {fmt!r}")

    serialized: str | Iterator[str] = serialize_config_diagnostics(
        meta=meta,
        config=config,
        fmt=fmt,
    )

    # Do not emit trailing newline for JSON
    nl: bool = fmt != OutputFormat.JSON
    emit_machine(serialized, nl=nl)


def emit_config_check_machine(
    *,
    meta: MetaPayload,
    config: Config,
    strict: bool,
    ok: bool,
    fmt: OutputFormat,
) -> None:
    """Emit `topmark config check` results in a machine-readable format.

    JSON:
      - One envelope: meta, config, config_diagnostics (full), summary.

    NDJSON:
      1) config
      2) config_diagnostics (counts-only)
      3) summary (command=config, subcommand=check)
      4+) diagnostic (domain=config) one per diagnostic

    Args:
        meta: The machine metadata payload.
        config: Immutable runtime configuration providing diagnostics.
        strict: Enforce strict config checking (fail on warning) if True,
            fail on error otherwise.
        ok: True if config checking passed, False otherwise.
        fmt: Target machine format (JSON or NDJSON).

    Raises:
        ValueError: if `fmt` is not a supported machine format.
    """
    if not is_machine_format(fmt):
        raise ValueError(f"Unsupported machine output format: {fmt!r}")

    serialized: str | Iterator[str] = serialize_config_check(
        meta=meta,
        config=config,
        strict=strict,
        ok=ok,
        fmt=fmt,
    )

    # Do not emit trailing newline for JSON
    nl: bool = fmt != OutputFormat.JSON
    emit_machine(serialized, nl=nl)


def emit_filetypes_machine(
    *,
    meta: MetaPayload,
    fmt: OutputFormat,
    show_details: bool,
) -> None:
    """Emit filetypes to ConsoleLike.

    Args:
        meta: The machine metadata payload.
        fmt: The output format.
        show_details: If True, show additional details.
    """
    serialized: str | Iterator[str] = serialize_filetypes(
        meta=meta,
        fmt=fmt,
        show_details=show_details,
    )

    # Do not emit trailing newline for JSON
    nl: bool = fmt != OutputFormat.JSON
    emit_machine(serialized, nl=nl)


def emit_processors_machine(
    *,
    meta: MetaPayload,
    fmt: OutputFormat,
    show_details: bool,
) -> None:
    """Emit processors to ConsoleLike.

    Args:
        meta: The machine metadata payload.
        fmt: The output format.
        show_details: If True, show additional details.
    """
    serialized: str | Iterator[str] = serialize_processors(
        meta=meta,
        fmt=fmt,
        show_details=show_details,
    )

    # Do not emit trailing newline for JSON
    nl: bool = fmt != OutputFormat.JSON
    emit_machine(serialized, nl=nl)
