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

from topmark.core.logging import get_logger
from topmark.pipeline.context.policy import check_permitted_by_policy
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import GenerationStatus
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.views import BuilderView
from topmark.utils.file import compute_relpath

if TYPE_CHECKING:
    from topmark.config.model import Config
    from topmark.core.logging import TopmarkLogger
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

        Return whether the builder has the prerequisites to compute field values.

        The builder should run whenever content is available, even for empty-like
        images. Empty-file insertion policy is a *mutation* concern and is handled
        later by planner/updater logic via `allow_insert_into_empty_like()`, not by
        `may_proceed()`.

        Args:
            ctx: The processing context for the current file.

        Returns:
            True if the builder can compute header field values for this context.
        """
        if ctx.is_halted:
            return False

        # Normal path:
        # - non-empty files require ContentStatus.OK
        # - empty files can proceed only when allowed by policy (also ContentStatus.OK)
        return ctx.status.content == ContentStatus.OK

    def run(self, ctx: ProcessingContext) -> None:
        """Build the field dictionaries used to render a TopMark header.

        This step analyzes the processing context and configuration to compute:
        * derived built‑in fields based on the file path; and
        * the final field mapping to be rendered (subset/overrides as per config).

        Args:
            ctx: The current processing context containing file info,
                configuration, and status.

        Mutations:
            - `ctx.views.build.builtins`: built‑in field mapping.
            - `ctx.views.build.selected`: selected/merged field mapping.
            - `ctx.status.generation`: updated to `GENERATED` or `NO_FIELDS`.

        Notes:
            Diagnostic messages are added if unknown header fields are referenced in
            `Config.header_fields` or when built‑ins are overridden by `Config.field_values`.

        Path semantics:
            - `file_path` is `ctx.path` as provided by config resolution.
              It may be relative or absolute depending on how the file was discovered.
            - `file_abspath` is computed from the logical header path and is therefore an
              absolute, normalized path. In stdin mode this means it reflects the logical
              `stdin_filename`, not the materialized temporary file path.
            - `file_relpath` and `relpath` are computed by calling
              `compute_relpath(file_path, relative_to)`. Note that this uses the
              original `file_path` (not `file_path.resolve()`), so the relative
              path is derived from the discovery spelling.
            - `relative_to` defaults to `Path.cwd()` when no explicit root is configured.
              If `Config.relative_to` is set, it is resolved to an absolute path via
              `Path(config.relative_to).resolve()`.
            - `relpath` becomes "." at repo root.

            This behavior intentionally keeps `file_relpath` stable for common cases
            like running TopMark from the repository root (so `pyproject.toml` yields
            `file_relpath = "pyproject.toml"`). If you need `file_relpath` computed
            relative to a specific root, set `Config.relative_to` (via config or CLI/API
            overrides).
        """
        logger.debug("ctx: %s", ctx)

        config: Config = ctx.config

        if check_permitted_by_policy(ctx) is False:
            ctx.status.generation = GenerationStatus.SKIPPED
            reason = "header field generation skipped by policy"
            ctx.diagnostics.add_info(reason)
            ctx.request_halt(reason=reason, at_step=self)
            return

        if not config.header_fields:
            # No header fields specified in the configuration
            ctx.status.generation = GenerationStatus.NO_FIELDS
            ctx.diagnostics.add_info("No header fields specified.")
            return

        file_path: Path = ctx.path

        # Prepare built-in fields related to the file system.
        #
        # STDIN content mode needs special care:
        #   - `ctx.path` is the *materialized* temp file that TopMark can read/write.
        #   - `config.stdin_filename` is a user-supplied *logical* filename that may not exist
        #     on disk (it is used only for metadata and discovery anchoring).
        #
        # Therefore:
        #   - `file` / `file_relpath` / `file_abspath` / `relpath` are derived from the logical
        #     header path.
        #   - `abspath` is still derived from the on-disk content path, since it represents the
        #     containing directory of the actual processed content.

        content_path: Path = file_path

        # In stdin mode, use `stdin_filename` (if provided) for logical header metadata.
        header_path: Path = (
            Path(ctx.config.stdin_filename)
            if (ctx.config.stdin_mode and ctx.config.stdin_filename)
            else content_path
        )

        # File absolute path is derived from the logical header path so stdin mode reports the
        # user-facing logical filename rather than the ephemeral materialized temp file.
        absolute_path: Path = header_path.resolve()
        content_absolute_path: Path = content_path.resolve(strict=True)

        # Relative paths are computed against `relative_to` using the logical header path.
        # Note: `header_path` may not exist, so `compute_relpath()` must not rely on
        # strict filesystem resolution.
        relative_to: Path = Path(config.relative_to).resolve() if config.relative_to else Path.cwd()
        # Determine relative path from the file to the root path
        # Default to the current working directory if 'relative_to' is not configured
        relative_path: Path = compute_relpath(header_path, relative_to)

        builtin_fields: dict[str, str] = {
            # Base file name (without any path)
            "file": header_path.name,
            # File name with its relative path
            "file_relpath": relative_path.as_posix(),
            # File name with its absolute path
            "file_abspath": absolute_path.as_posix(),
            # Parent directory path (relative)
            "relpath": relative_path.parent.as_posix() if relative_path else "",
            # Parent directory path (absolute, of actual content)
            "abspath": content_absolute_path.parent.as_posix(),
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
                ctx.diagnostics.add_warning(f"Redefined built-in fields: {builtin_overlap_repr}")

        # Merge built‑ins with configuration‑defined values; allow overrides; restrict
        # to header_fields.
        all_fields: dict[str, str] = {
            **builtin_fields,
            **config.field_values,
        }

        result: dict[str, str] = {}

        for key in config.header_fields:
            value: str | None = all_fields.get(key)
            if value is None:
                ctx.diagnostics.add_error(f"Unknown header field: {key}")
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
            ctx: The processing context.
        """
        st: GenerationStatus = ctx.status.generation

        # May proceed to next step (always):
        if st == GenerationStatus.GENERATED:
            pass  # expected path; silent
        # May proceed to next step (render empty header):
        elif st == GenerationStatus.NO_FIELDS:
            ctx.hint(
                axis=Axis.GENERATION,
                code=KnownCode.GENERATION_NO_FIELDS,
                cluster=Cluster.BLOCKED_POLICY,
                message="no header fields configured",
                terminal=False,
            )
        # Stop processing:
        elif st == GenerationStatus.SKIPPED:
            ctx.hint(
                axis=Axis.GENERATION,
                code=KnownCode.PLAN_SKIP,
                cluster=Cluster.BLOCKED_POLICY,
                message="header field generation skipped",
                terminal=True,
            )
        elif st == GenerationStatus.PENDING:
            # builder did not complete
            ctx.request_halt(reason=f"{self.__class__.__name__} did not set state.", at_step=self)
