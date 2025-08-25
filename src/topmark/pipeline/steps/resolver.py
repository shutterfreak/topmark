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
from topmark.filetypes.base import FileType
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

    # Attempt to match the path against each registered FileType,
    # then pick the most specific match.
    candidates: list[tuple[int, str, FileType]] = []

    path_str = str(ctx.path.as_posix())
    base_name = ctx.path.name

    def _score(ft: FileType) -> int:
        """Higher score = more specific match."""
        s = 0
        # 1) Explicit filename / tail subpath matches (e.g., ".vscode/settings.json")
        for fname in getattr(ft, "filenames", []) or []:
            # exact filename or ending subpath match
            if base_name == fname or path_str.endswith(fname):
                # prefer longer names (more specific)
                s = max(s, 100 + min(len(fname), 100))
        # 2) Extension matches (lower precedence than explicit filename)
        for ext in getattr(ft, "extensions", []) or []:
            if base_name.endswith(ext):
                s = max(s, 50 + min(len(ext), 10))
        # 3) Regex patterns: we can’t introspect without duplicating ft.matches(),
        # but when ft.matches() succeeds (see below), give a medium baseline bump
        # if the type actually declares patterns.
        if getattr(ft, "patterns", []):
            s = max(s, 70)
        # 4) Prefer headerable types on ties
        if not getattr(ft, "skip_processing", False):
            s += 1
        return s

    # Collect all file types that match
    for ft in get_file_type_registry().values():
        if ft.matches(ctx.path):
            candidates.append((_score(ft), ft.name, ft))

    if candidates:
        # Best by (score DESC, name ASC) for deterministic choice
        candidates.sort(key=lambda x: (-x[0], x[1]))
        _, _, file_type = candidates[0]

        ctx.file_type = file_type
        logger.debug("File '%s' resolved to type: %s", ctx.path, file_type.name)

        if file_type.skip_processing:
            ctx.status.file = FileStatus.SKIPPED_KNOWN_NO_HEADERS
            ctx.diagnostics.append(
                f"File type '{file_type.name}' recognized; "
                "headers are not supported for this format. Skipping."
            )
            logger.info(
                "Skipping header processing for '%s' (file type '%s' marked skip_processing=True)",
                ctx.path,
                file_type.name,
            )
            return ctx

        # Matched a FileType, but no header processor is registered for it
        processor = get_header_processor_registry().get(file_type.name)
        if processor is None:
            ctx.status.file = (
                FileStatus.SKIPPED_NO_HEADER_PROCESSOR
            )  # or SKIPPED_NO_HEADER_MANAGER if that's your enum
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
