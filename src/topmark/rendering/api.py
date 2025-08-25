# topmark:header:start
#
#   file         : api.py
#   file_relpath : src/topmark/rendering/api.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""API for rendering TopMark headers.

This module provides functions to render TopMark headers for given file paths
using the configured processing pipelines. It serves as the high-level
interface for converting configuration and overrides into a formatted header string.
"""

from dataclasses import replace
from pathlib import Path

from topmark.config import Config
from topmark.pipeline import runner
from topmark.pipeline.context import ProcessingContext
from topmark.rendering.formats import HeaderOutputFormat

from ..pipeline.pipelines import get_pipeline


def render_header_for_path(
    config: Config,
    path: Path,
    header_overrides: dict[str, str] | None = None,
    header_fields_overrides: list[str] | None = None,
    format_override: HeaderOutputFormat | None = None,
    # newline: str = "\n",
) -> str:
    """Render a TopMark header for a given file path using the render pipeline.

    This function prepares an effective configuration (including optional overrides),
    bootstraps a processing context, and executes the "render" pipeline to produce
    the header text for the specified file.

    Args:
        config (Config): Effective TopMark configuration to use.
        path (Path): Target file path whose file type determines the processor.
        header_overrides (dict[str, str] | None): Optional mapping of field overrides
            to inject into the header.
        header_fields_overrides (list[str] | None): Optional explicit field order
            to render instead of the default.
        format_override (HeaderOutputFormat | None): Optional explicit header output
            format to use. Defaults to ``HeaderOutputFormat.NATIVE``.

    Returns:
        str: The rendered header as a single string (joined lines).
    """
    # Work on a copy; never mutate the caller's config
    eff_config = replace(config)

    # Effective format and field order
    eff_config.header_format = (
        format_override or eff_config.header_format or HeaderOutputFormat.NATIVE
    )
    eff_config.header_fields = header_fields_overrides or config.header_fields

    # Merge field values (config → overrides) for the effective field order
    effective_fields = eff_config.header_fields
    merged: dict[str, str] = {k: config.field_values.get(k, "") for k in effective_fields}
    if header_overrides:
        merged.update(header_overrides)
    eff_config.field_values = merged

    # Get the pipeline steps
    steps = get_pipeline("render")
    # Bootstrap the context with the effective config
    context = ProcessingContext.bootstrap(path=path, config=eff_config)
    # Run the pipeline
    context = runner.run(context, steps)
    # Return the header

    return context.expected_header_block or ""
