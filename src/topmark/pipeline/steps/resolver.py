# topmark:header:start
#
#   file         : resolver.py
#   file_relpath : src/topmark/pipeline/steps/resolver.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""File type and header processor resolver step for the TopMark pipeline.

This step determines the `FileType` for the current path and attaches the
corresponding `HeaderProcessor` instance from the registry. It updates
`ctx.status.file` accordingly and records diagnostics for unsupported files or
missing processors. It performs no I/O.
"""

from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.constants import VALUE_NOT_SET
from topmark.filetypes.instances import get_file_type_registry
from topmark.filetypes.registry import get_header_processor_registry
from topmark.pipeline.context import FileStatus, ProcessingContext

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def resolve(ctx: ProcessingContext) -> ProcessingContext:
    """Resolve and assign the file type and header processor for the file.

    Updates these fields on the context when successful: `ctx.file_type`,
    `ctx.header_processor`, and `ctx.status.file`. On failure it appends a
    human-readable diagnostic and sets an appropriate file status.

    Args:
        ctx: Processing context representing the file being handled.

    Returns:
        ProcessingContext: The same context, updated in place.
    """
    logger.debug(
        "Resolve start: file='%s', status='%s', type=%s, processor=%s",
        ctx.path,
        ctx.status.file.value,
        getattr(ctx.file_type, "name", VALUE_NOT_SET),
        (ctx.header_processor.__class__.__name__ if ctx.header_processor else VALUE_NOT_SET),
    )

    # Attempt to match the path against each registered FileType
    for file_type in get_file_type_registry().values():
        if file_type.matches(ctx.path):
            ctx.file_type = file_type
            logger.debug("File '%s' resolved to type: %s", ctx.path, file_type.name)

            if file_type.skip_processing:
                ctx.status.file = FileStatus.SKIPPED_KNOWN_NO_HEADERS
                ctx.diagnostics.append(
                    f"File type '{file_type.name}' recognized; "
                    "headers are not supported for this format. Skipping."
                )
                logger.info(
                    "Skipping header processing for '%s' "
                    "(file type '%s' marked skip_processing=True)",
                    ctx.path,
                    file_type.name,
                )
                return ctx

            # Matched a FileType, but no header processor is registered for it
            processor = get_header_processor_registry().get(file_type.name)
            if processor is None:
                ctx.status.file = FileStatus.SKIPPED_NO_HEADER_PROCESSOR
                ctx.diagnostics.append(
                    f"No header processor registered for file type '{file_type.name}'."
                )
                logger.info(
                    "No header processor registered for file type '%s' (file '%s')",
                    file_type.name,
                    ctx.path,
                )
                return ctx

            # Success: attach the processor and mark the file as resolved
            ctx.header_processor = processor
            ctx.status.file = FileStatus.RESOLVED
            logger.debug(
                "Resolve success: file='%s' type='%s' processor=%s",
                ctx.path,
                file_type.name,
                processor.__class__.__name__,
            )
            return ctx

    # No FileType matched: mark as unsupported and record a diagnostic
    ctx.status.file = FileStatus.SKIPPED_UNSUPPORTED
    ctx.diagnostics.append("No file type associated with this file.")
    logger.info("Unsupported file type for '%s' (no matcher)", ctx.path)
    return ctx
