# topmark:header:start
#
#   project      : TopMark
#   file         : builder.py
#   file_relpath : src/topmark/pipeline/steps/builder.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Builder step for TopMark pipeline.

This step computes the **field dictionaries** that will later be rendered into a
TopMark header. It derives built‑in fields from the filesystem (e.g., `file`,
`file_relpath`) and merges them with `Config.field_values`, then selects only
those keys listed in `Config.header_fields`.

Outputs:
  * `ctx.views.build.builtins`: the derived built‑in field mapping.
  * `ctx.views.build.selected`: the filtered/merged mapping to be rendered by the renderer.
  * `ctx.status.generation`: set to `GENERATED` (or `NO_FIELDS` when no fields are
    configured).

Notes:
  This step does **not** render text. The renderer consumes `ctx.views.build.selected`
  and produces the final lines/block in `ctx.views.render`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from topmark.config.logging import get_logger
from topmark.pipeline.context.policy import allow_empty_by_policy, check_permitted_by_policy
from topmark.pipeline.hints import Axis, Cluster, KnownCode, make_hint
from topmark.pipeline.status import ContentStatus, FsStatus, GenerationStatus
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.views import BuilderView
from topmark.utils.file import compute_relpath

if TYPE_CHECKING:
    from topmark.config import Config
    from topmark.config.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext

logger: TopmarkLogger = get_logger(__name__)


class BuilderStep(BaseStep):
    """Compute field dictionaries for rendering a TopMark header.

    Derives built-in fields from the filesystem, merges with configured values,
    and selects only configured header fields. Produces a `BuilderView`.

    Axes written:
      - generation

    Sets:
      - GenerationStatus: {PENDING, GENERATED, NO_FIELDS}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.GENERATION,
            axes_written=(Axis.GENERATION,),
        )

    def may_proceed(self, ctx: ProcessingContext) -> bool:
        """Determine if processing can proceed to the build step.

        Processing can proceed if:
        - The file was successfully resolved (ctx.status.resolve is RESOLVED)
        - A header processor is available (ctx.header_processor is not None)
        - The file image is available (via `ctx.views.image`).

        Args:
            ctx (ProcessingContext): The processing context for the current file.

        Returns:
            bool: True if processing can proceed to the build step, False otherwise.
        """
        if ctx.flow.halt:
            return False

        # Do not generate headers for empty files when policy forbids it.
        # We only allow generation for empty files if the effective policy
        # explicitly permits inserting headers into empty files.
        if ctx.status.fs == FsStatus.EMPTY and not allow_empty_by_policy(ctx):
            return False

        # Normal path:
        # - non-empty files require ContentStatus.OK
        # - empty files can proceed only when allowed by policy
        return ctx.status.content == ContentStatus.OK or allow_empty_by_policy(ctx)

    def run(self, ctx: ProcessingContext) -> None:
        """Build the field dictionaries used to render a TopMark header.

        This step analyzes the processing context and configuration to compute:
        * derived built‑in fields based on the file path; and
        * the final field mapping to be rendered (subset/overrides as per config).

        Args:
            ctx (ProcessingContext): The current processing context containing file info,
                configuration, and status.

        Mutations:
            - `ctx.views.build.builtins`: built‑in field mapping.
            - `ctx.views.build.selected`: selected/merged field mapping.
            - `ctx.status.generation`: updated to `GENERATED` or `NO_FIELDS`.

        Notes:
            Diagnostic messages are added if unknown header fields are referenced in
            `Config.header_fields` or when built‑ins are overridden by `Config.field_values`.
        """
        logger.debug("ctx: %s", ctx)

        config: Config = ctx.config

        if check_permitted_by_policy(ctx) is False:
            ctx.status.generation = GenerationStatus.SKIPPED
            reason = "header field generation skipped by policy"
            logger.debug(reason)
            ctx.add_info(reason)
            ctx.stop_flow(reason=reason, at_step=self)

        if not config.header_fields:
            # No header fields specified in the configuration
            ctx.status.generation = GenerationStatus.NO_FIELDS
            logger.debug("No header fields specified.")
            return

        file_path: Path = ctx.path
        result: dict[str, str] = {}

        # Prepare built-in fields related to the file system
        # Resolve absolute paths first for consistency
        absolute_path: Path = file_path.resolve(strict=True)
        relative_to: Path = Path(config.relative_to).resolve() if config.relative_to else Path.cwd()
        # Determine relative path from the file to the root path
        # Default to the current working directory if 'relative_to' is not configured
        relative_path: Path = compute_relpath(file_path, relative_to)

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

        # Merge in any additional fields from the configuration (may override built‑ins).
        if config.field_values:
            # Warn if configuration fields override built-in fields (potentially accidental)
            builtin_overlap: list[str] = [
                key for key in config.field_values if key in builtin_fields
            ]
            if len(builtin_overlap) > 0:
                builtin_overlap_repr: str = ", ".join(
                    key for key in config.field_values if key in builtin_fields
                )
                logger.warning(
                    "Config.field_values contains keys that overlap with builtin fields: %s",
                    builtin_overlap_repr,
                )
                ctx.add_warning(f"Redefined built-in fields: {builtin_overlap_repr}")

        # Merge built‑ins with configuration‑defined values; allow overrides; restrict
        # to header_fields.
        all_fields: dict[str, str] = {
            **builtin_fields,
            **config.field_values,
        }

        for key in config.header_fields:
            value: str | None = all_fields.get(key)
            if value is None:
                logger.warning("Unknown header field: %s", key)
                ctx.add_error(f"Unknown header field: {key}")
            else:
                result[key] = value

        # Populate BuilderView with builtins and selected field mappings
        ctx.views.build = BuilderView(builtins=builtin_fields, selected=result)
        # Populate RenderView with mapping only; lines/block are filled by renderer
        ctx.status.generation = GenerationStatus.GENERATED

        logger.debug(
            "Builder: %s – header status=%s, selected fields:\n%s",
            ctx.path,
            ctx.status.header.value,
            "\n".join(
                f"  {key:<20} : {value}" for key, value in (ctx.views.build.selected or {}).items()
            ),
        )
        logger.info(
            "Builder completed for %s: header status=%s, generation status=%s",
            ctx.path,
            ctx.status.header.value,
            ctx.status.generation.value,
        )

        return

    def hint(self, ctx: ProcessingContext) -> None:
        """Attach generation hints (non-binding).

        Args:
            ctx (ProcessingContext): The processing context.
        """
        st: GenerationStatus = ctx.status.generation

        # May proceed to next step (always):
        if st == GenerationStatus.GENERATED:
            pass  # expected path; silent
        # May proceed to next step (render empty header):
        elif st == GenerationStatus.NO_FIELDS:
            ctx.add_hint(
                make_hint(
                    axis=Axis.GENERATION,
                    code=KnownCode.GENERATION_NO_FIELDS,
                    cluster=Cluster.BLOCKED_POLICY,
                    message="no header fields configured",
                    terminal=False,
                )
            )
        # Stop processing:
        elif st == GenerationStatus.SKIPPED:
            ctx.add_hint(
                make_hint(
                    axis=Axis.GENERATION,
                    code=KnownCode.PLAN_SKIP,
                    cluster=Cluster.BLOCKED_POLICY,
                    message="header field generation skipped",
                    terminal=True,
                )
            )
        elif st == GenerationStatus.PENDING:
            # builder did not complete
            ctx.stop_flow(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
