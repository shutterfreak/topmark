# topmark:header:start
#
#   file         : builder.py
#   file_relpath : src/topmark/pipeline/steps/builder.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Builder step for TopMark pipeline.

This step builds a dictionary containing the expected (updated) header fields for a file,
based on the pipeline context and configuration. It produces the `expected_header_dict`
in the context, updates built-in fields, and sets the generation status accordingly.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.pipeline.context import FileStatus, GenerationStatus, ProcessingContext
from topmark.utils.file import compute_relpath

if TYPE_CHECKING:
    from topmark.config import Config

logger = get_logger(__name__)


def build(ctx: ProcessingContext) -> ProcessingContext:
    """Build the dict with expected (updated) header fields.

    This step analyzes the processing context and configuration to determine the
    expected header fields for the current file. It sets built-in fields related
    to file paths and combines them with any additional user-defined fields.

    Args:
        ctx (ProcessingContext): The current processing context containing file info,
            configuration, and status.

    Returns:
        ProcessingContext: The updated processing context with the expected header
            dictionary and updated generation status.

    Notes:
        Diagnostics messages are added if unknown or missing header fields are detected.
    """
    # Safeguard: Skip if file status is not ready for building headers
    if ctx.status.file not in (FileStatus.RESOLVED, FileStatus.EMPTY_FILE):
        return ctx
    if ctx.header_processor is None:
        return ctx

    if not ctx.config.header_fields:
        # No header fields specified in the configuration
        ctx.status.generation = GenerationStatus.NO_FIELDS
        logger.debug("No header fields specified.")
        return ctx

    config: Config = ctx.config
    file_path: Path = ctx.path
    result: dict[str, str] = {}

    # Prepare built-in fields related to the file system
    # Resolve absolute paths first for consistency
    absolute_path = file_path.resolve(strict=True)
    relative_to = Path(config.relative_to).resolve() if config.relative_to else Path.cwd()
    # Determine relative path from the file to the root path
    # Default to the current working directory if 'relative_to' is not configured
    relative_path = compute_relpath(file_path, relative_to)

    builtin_fields: dict[str, str] = {
        # Base file name (without any path)
        "file": file_path.name,
        # File name with its relative path
        "file_relpath": relative_path.as_posix(),
        # File name with its absolute path
        "file_abspath": absolute_path.as_posix(),
        # Parent directory path (relative)
        "relpath": relative_path.parent.as_posix() if relative_path else "",
        # Parent directory path (absolute)
        "abspath": absolute_path.parent.as_posix() if absolute_path else "",
    }

    ctx.builtin_fields = builtin_fields

    # Merge in any additional fields from the configuration
    if config.field_values:
        # Warn if configuration fields override built-in fields (potentially accidental)
        builtin_overlap: list[str] = [key for key in config.field_values if key in builtin_fields]
        if len(builtin_overlap) > 0:
            builtin_overlap_repr = ", ".join(
                key for key in config.field_values if key in builtin_fields
            )
            logger.warning(
                "Config.field_values contains keys that overlap with builtin fields: %s",
                builtin_overlap_repr,
            )
            ctx.diagnostics = (ctx.diagnostics or []) + [
                f"Redefined built-in fields: {builtin_overlap_repr}"
            ]

    # Merge built-in and configuration-defined fields
    # Allow user-defined fields to override built-ins when both are in config.field_values
    # Restrict to fields listed in config.header_fields
    all_fields: dict[str, str] = {
        **builtin_fields,
        **config.field_values,
    }

    for key in config.header_fields:
        value = all_fields.get(key)
        if value is None:
            logger.warning("Unknown header field: %s", key)
            ctx.diagnostics.append(f"Unknown header field: {key}")
        else:
            result[key] = value

    ctx.expected_header_dict = result
    ctx.status.generation = GenerationStatus.GENERATED

    logger.debug(
        "File '%s' : header status %s, expected fields:\n%s",
        ctx.path,
        ctx.status.header.value,
        "\n".join(
            f"  {key:<20} : {value}" for key, value in (ctx.expected_header_dict or {}).items()
        ),
    )
    logger.info(
        "Phase 3 - Scanned file %s: header status: %s, generation status: %s",
        ctx.path,
        ctx.status.header.value,
        ctx.status.generation.value,
    )

    return ctx
