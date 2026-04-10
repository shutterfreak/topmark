# topmark:header:start
#
#   project      : TopMark
#   file         : machine.py
#   file_relpath : src/topmark/cli/emitters/machine.py
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

from topmark.cli.console.context import resolve_console
from topmark.config.machine.serializers import serialize_config
from topmark.config.machine.serializers import serialize_config_check
from topmark.config.machine.serializers import serialize_config_diagnostics
from topmark.core.formats import OutputFormat
from topmark.core.formats import is_machine_format
from topmark.pipeline.machine.serializers import serialize_processing_results
from topmark.registry.machine.serializers import serialize_bindings
from topmark.registry.machine.serializers import serialize_filetypes
from topmark.registry.machine.serializers import serialize_processors

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator

    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.config.model import Config
    from topmark.core.machine.schemas import MetaPayload
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.toml.resolution import ResolvedTopmarkTomlSources


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

    console: ConsoleProtocol = resolve_console()
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
    resolved_toml: ResolvedTopmarkTomlSources | None = None,
    show_config_layers: bool = False,
) -> None:
    """Emit the effective Config snapshot in a machine-readable format.

    When `show_config_layers` is enabled, machine output also includes a
    `config_provenance` payload that preserves ordered config layers and the
    corresponding source-local TOML fragments.

    Shapes:
        - JSON, default:
            {"meta": ..., "config": ...}
        - JSON, with provenance:
            {"meta": ..., "config_provenance": ..., "config": ...}
        - NDJSON, default:
            {"kind": "config", "meta": ..., "config": ...}
        - NDJSON, with provenance:
            {"kind": "config_provenance", "meta": ..., "config_provenance": ...}
            {"kind": "config", "meta": ..., "config": ...}

    Args:
        meta: The machine metadata payload.
        config: Immutable runtime configuration to serialize.
        fmt: Target machine format (JSON or NDJSON).
        resolved_toml: Resolved TOML sources used to build optional machine-readable
            config provenance.
        show_config_layers: If `True`, include layered config provenance in the
            machine output.

    Raises:
        ValueError: If `fmt` is not a supported machine format, or if show_config_layers is `True`
            but resolved_toml is `None`.


    """
    if not is_machine_format(fmt):
        raise ValueError(f"Unsupported machine output format: {fmt!r}")

    serialized: str | Iterator[str] = serialize_config(
        meta=meta,
        config=config,
        fmt=fmt,
        resolved_toml=resolved_toml,
        show_config_layers=show_config_layers,
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
      - One envelope containing `meta`, `config`, `config_diagnostics`, and
        `config_check`.

    NDJSON:
      1) `config`
      2) `config_diagnostics` (counts-only)
      3) `config_check` (command=`config`, subcommand=`check`)
      4+) `diagnostic` (domain=`config`) one per diagnostic

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
    """Emit `topmark registry filetypes` machine output.

    Args:
        meta: The machine metadata payload.
        fmt: Target machine format (`json` or `ndjson`).
        show_details: If True, include expanded identity, matching, binding,
            and policy fields.
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
    """Emit `topmark registry processors` machine output.

    Args:
        meta: The machine metadata payload.
        fmt: Target machine format (`json` or `ndjson`).
        show_details: If True, include expanded identity, binding, and
            delimiter fields.
    """
    serialized: str | Iterator[str] = serialize_processors(
        meta=meta,
        fmt=fmt,
        show_details=show_details,
    )

    # Do not emit trailing newline for JSON
    nl: bool = fmt != OutputFormat.JSON
    emit_machine(serialized, nl=nl)


def emit_bindings_machine(
    *,
    meta: MetaPayload,
    fmt: OutputFormat,
    show_details: bool,
) -> None:
    """Emit `topmark registry bindings` machine output.

    Args:
        meta: The machine metadata payload.
        fmt: Target machine format (`json` or `ndjson`).
        show_details: If True, include expanded file type and processor
            identity metadata for each binding plus structured auxiliary lists.
    """
    serialized: str | Iterator[str] = serialize_bindings(
        meta=meta,
        fmt=fmt,
        show_details=show_details,
    )

    # Do not emit trailing newline for JSON
    nl: bool = fmt != OutputFormat.JSON
    emit_machine(serialized, nl=nl)
