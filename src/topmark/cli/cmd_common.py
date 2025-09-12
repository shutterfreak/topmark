# topmark:header:start
#
#   project      : TopMark
#   file         : cmd_common.py
#   file_relpath : src/topmark/cli/cmd_common.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Common command utilities for Click-based commands.

This module holds small, focused helpers used by multiple CLI commands.
They intentionally avoid policy (exit code rules, messages) and only
encapsulate plumbing such as running pipelines, filtering, and error exits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from topmark.cli.config_resolver import resolve_config_from_click
from topmark.cli.console_helpers import get_console_safely
from topmark.cli_shared.exit_codes import ExitCode
from topmark.config.logging import get_logger
from topmark.file_resolver import resolve_file_list
from topmark.pipeline import runner
from topmark.pipeline.context import ComparisonStatus, FileStatus, ProcessingContext
from topmark.pipeline.pipelines import get_pipeline

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.cli.io import InputPlan
    from topmark.config import Config, MutableConfig
    from topmark.rendering.formats import HeaderOutputFormat

logger = get_logger(__name__)


def get_effective_verbosity(ctx: click.Context, config: "Config | None" = None) -> int:
    """Return the effective program-output verbosity for this command.

    Resolution order (tri-state aware):
        1. Config.verbosity_level if set (not None)
        2. ctx.obj["verbosity_level"] if present
        3. 0 (terse)
    """
    cfg_level = getattr(config, "verbosity_level", None) if config else None
    if cfg_level is not None:
        return int(cfg_level)
    return int(ctx.obj.get("verbosity_level", 0))


def build_file_list(config: Config, *, stdin_mode: bool, temp_path: Path | None) -> list[Path]:
    """Return the files to process, respecting STDIN content mode.

    - If content-on-STDIN mode, return the single temp path.
    - Otherwise, delegate to the unified resolver that uses `config.files`,
      `files_from`, include/exclude patterns, and file types.
    """
    if stdin_mode:
        assert temp_path is not None
        return [temp_path]
    return resolve_file_list(config)


def run_steps_for_files(
    file_list: list[Path],
    *,
    pipeline_name: str,
    config: Config,
) -> tuple[list[ProcessingContext], ExitCode | None]:
    """Run a pipeline for each file and return (results, encountered_error_code).

    Catches common filesystem/encoding errors so command bodies don’t duplicate try/except.

    Exit code mapping:
        FILE_NOT_FOUND → FileNotFoundError / IsADirectoryError
        PERMISSION_DENIED → PermissionError
        ENCODING_ERROR → UnicodeDecodeError
        PIPELINE_ERROR → any other unexpected exception
    """
    console = get_console_safely()
    steps = get_pipeline(pipeline_name)
    results: list[ProcessingContext] = []
    encountered_error_code: ExitCode | None = None

    for path in file_list:
        try:
            ctx_obj: ProcessingContext = ProcessingContext.bootstrap(path=path, config=config)
            ctx_obj = runner.run(ctx_obj, steps)
            results.append(ctx_obj)
        except (FileNotFoundError, PermissionError, IsADirectoryError) as e:
            logger.error("Filesystem error while processing %s: %s", path, e)
            console.error(f"❌ Filesystem error processing {path}: {e}")
            if isinstance(e, (FileNotFoundError, IsADirectoryError)):
                logger.error("%s: %s", e, path)
                encountered_error_code = encountered_error_code or ExitCode.FILE_NOT_FOUND
            else:
                logger.error("%s: %s", e, path)
                encountered_error_code = encountered_error_code or ExitCode.PERMISSION_DENIED
            continue
        except UnicodeDecodeError as e:
            logger.error("Encoding error while reading %s: %s", path, e)
            console.error(f"🧵 Encoding error in {path}: {e}")
            encountered_error_code = encountered_error_code or ExitCode.ENCODING_ERROR
            continue
        except Exception as e:  # pragma: no cover
            logger.exception("Unexpected error processing %s", path)
            console.error(f"⚠️  Unexpected error processing {path}: {e} (use -vv for traceback)")
            encountered_error_code = encountered_error_code or ExitCode.PIPELINE_ERROR
            continue

    return results, encountered_error_code


def filter_view_results(
    results: list[ProcessingContext],
    *,
    skip_compliant: bool,
    skip_unsupported: bool,
) -> list[ProcessingContext]:
    """Apply --skip-compliant and --skip-unsupported filters to a results list.

    Args:
        results (list[ProcessingContext]): Full list of ProcessingContext results.
        skip_compliant (bool): If True, filter out files that are compliant/unchanged.
        skip_unsupported (bool): If True, filter out files that were skipped as unsupported.

    Returns:
        list[ProcessingContext]: Filtered list of ProcessingContext results.
    """
    view = results
    if skip_compliant:
        view = [r for r in view if r.status.comparison is not ComparisonStatus.UNCHANGED]
    if skip_unsupported:
        view = [
            r
            for r in view
            if r.status.file
            not in {FileStatus.SKIPPED_UNSUPPORTED, FileStatus.SKIPPED_KNOWN_NO_HEADERS}
        ]
    return view


def exit_if_no_files(file_list: list[Path]) -> bool:
    """Echo a friendly message and return True if there is nothing to process."""
    if not file_list:
        console = get_console_safely()
        console.print(console.styled("\nℹ️  No files to process.\n", fg="blue"))
        return True
    return False


def maybe_exit_on_error(*, code: ExitCode | None, temp_path: Path | None) -> None:
    """If an error code was encountered, cleanup and exit with it."""
    if code is not None:
        from topmark.cli_shared.utils import safe_unlink

        safe_unlink(temp_path)
        click.get_current_context().exit(code)


def build_config_common(
    *,
    ctx: click.Context,
    plan: InputPlan,
    no_config: bool,
    config_paths: list[str],
    file_types: list[str],
    relative_to: str | None,
    align_fields: bool,
    header_format: HeaderOutputFormat | None,
) -> MutableConfig:
    """Materialize Config from an input plan (no file list resolution)."""
    return resolve_config_from_click(
        ctx=ctx,
        verbosity_level=ctx.obj.get("verbosity_level"),
        apply_changes=ctx.obj.get("apply_changes"),
        files=plan.paths,
        files_from=plan.files_from,
        stdin=plan.stdin_mode,
        include_patterns=plan.include_patterns,
        include_from=plan.include_from,
        exclude_patterns=plan.exclude_patterns,
        exclude_from=plan.exclude_from,
        file_types=file_types,
        relative_to=relative_to,
        no_config=no_config,
        config_paths=config_paths,
        align_fields=align_fields,
        header_format=header_format,
    )
