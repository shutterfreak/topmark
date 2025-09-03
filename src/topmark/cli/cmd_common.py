# topmark:header:start
#
#   file         : cmd_common.py
#   file_relpath : src/topmark/cli/cmd_common.py
#   project      : TopMark
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

from pathlib import Path
from typing import TYPE_CHECKING

import click

from topmark.cli.config_resolver import resolve_config_from_click
from topmark.cli_shared.exit_codes import ExitCode
from topmark.config.logging import get_logger
from topmark.file_resolver import resolve_file_list
from topmark.pipeline import runner
from topmark.pipeline.context import ComparisonStatus, FileStatus, ProcessingContext
from topmark.pipeline.pipelines import get_pipeline

if TYPE_CHECKING:
    from topmark.cli.io import InputPlan
    from topmark.config import Config
    from topmark.rendering.formats import HeaderOutputFormat

logger = get_logger(__name__)


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
            click.secho(f"❌ Filesystem error processing {path}: {e}", fg="red")
            if isinstance(e, (FileNotFoundError, IsADirectoryError)):
                logger.error("%s: %s", e, path)
                encountered_error_code = encountered_error_code or ExitCode.FILE_NOT_FOUND
            else:
                logger.error("%s: %s", e, path)
                encountered_error_code = encountered_error_code or ExitCode.PERMISSION_DENIED
            continue
        except UnicodeDecodeError as e:
            logger.error("Encoding error while reading %s: %s", path, e)
            click.secho(f"🧵 Encoding error in {path}: {e}", fg="red")
            encountered_error_code = encountered_error_code or ExitCode.ENCODING_ERROR
            continue
        except Exception as e:  # pragma: no cover
            logger.exception("Unexpected error processing %s", path)
            click.secho(
                f"⚠️  Unexpected error processing {path}: {e} (use -vv for traceback)", fg="red"
            )
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
        results: Full list of ProcessingContext results.
        skip_compliant: If True, filter out files that are compliant/unchanged.
        skip_unsupported: If True, filter out files that were skipped as unsupported.

    Returns:
        Filtered list of ProcessingContext results.
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
        click.secho("\nℹ️  No files to process.\n", fg="blue")
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
) -> Config:
    """Materialize Config from an input plan (no file list resolution)."""
    return resolve_config_from_click(
        ctx=ctx,
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


def build_config_and_file_list(
    *,
    ctx: click.Context,
    plan: InputPlan,
    no_config: bool,
    config_paths: list[str],
    file_types: list[str],
    relative_to: str | None,
    align_fields: bool,
    header_format: HeaderOutputFormat | None,
) -> tuple[Config, list[Path]]:
    """Materialize Config and file list from an input plan."""
    if plan.stdin_mode:
        config = resolve_config_from_click(
            ctx=ctx,
            files=plan.paths,
            files_from=plan.files_from,
            stdin=True,
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
        return config, [Path(plan.paths[0])]
    else:
        config = resolve_config_from_click(
            ctx=ctx,
            files=plan.paths,
            files_from=plan.files_from,
            stdin=False,
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
        return config, resolve_file_list(config)
