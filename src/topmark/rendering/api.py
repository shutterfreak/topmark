# topmark:header:start
#
#   project      : TopMark
#   file         : api.py
#   file_relpath : src/topmark/rendering/api.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""API for rendering TopMark headers.

This module provides functions to render TopMark headers for given file paths
using the configured processing pipelines. It serves as the high-level
interface for converting configuration and overrides into a formatted header string.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from topmark.config import Config
from topmark.pipeline import runner
from topmark.pipeline.context import ProcessingContext
from topmark.rendering.formats import HeaderOutputFormat

from ..pipeline.pipelines import Pipeline

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.config import Config
    from topmark.pipeline.contracts import Step
    from topmark.pipeline.views import RenderView


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
    # Prepare effective values without mutating the original Config (it's frozen)

    # Compute the effective format (override > config > default)
    effective_format: HeaderOutputFormat = (
        format_override or config.header_format or HeaderOutputFormat.NATIVE
    )

    # Compute effective field order (override > config)
    effective_fields: tuple[str, ...] = (
        tuple(header_fields_overrides)
        if header_fields_overrides is not None
        else config.header_fields
    )

    # Merge values (config → overrides) in the chosen field order
    merged: dict[str, str] = {k: config.field_values.get(k, "") for k in effective_fields}
    if header_overrides:
        merged.update(header_overrides)

    # Build an effective frozen snapshot for the renderer
    eff_config: Config = replace(
        config,
        header_format=effective_format,
        header_fields=effective_fields,
        field_values=merged,
    )

    # Get the pipeline steps
    pipeline: Sequence[Step] = Pipeline.CHECK_RENDER.steps

    # Bootstrap the context with the effective config
    context: ProcessingContext = ProcessingContext.bootstrap(path=path, config=eff_config)
    # Run the pipeline
    context = runner.run(context, pipeline)
    # Return the header

    rennder_view: RenderView | None = context.views.render
    if rennder_view:
        return rennder_view.block or ""
    return ""
