# topmark:header:start
#
#   project      : TopMark
#   file         : status.py
#   file_relpath : src/topmark/pipeline/context/status.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Status types and helpers for per-axis progress tracking in the TopMark pipeline.

This module defines the core dataclasses and typed payloads used to represent
per-axis status within the TopMark processing pipeline. Each pipeline axis
(resolve, fs, content, header, generation, render, strip, comparison, plan,
patch, write) exposes its own status enum, and
[HeaderProcessingStatus][topmark.pipeline.context.status.HeaderProcessingStatus]
collects these into a single structure that serves as the authoritative source
of truth for all status evaluation.

The supporting
[AxisStatusPayload][topmark.pipeline.context.status.AxisStatusPayload] provides
a stable, JSON-serializable representation used in machine output
(`--json` / NDJSON), ensuring that external tools can reliably consume pipeline
results without depending on internal enum details.

A small
[StepStatus][topmark.pipeline.context.status.StepStatus] value object is also
provided for step-level diagnostics, enabling the runner and CLI to report
per-step outcomes without exposing internal step implementation details.

Sections:
    AxisStatusPayload:
        TypedDict describing the serializable payload for a single axis.

    HeaderProcessingStatus:
        Aggregated structure holding the current status for all pipeline axes.
        Used by steps, the runner, and the CLI as the unified representation
        of pipeline progress and outcomes.

    StepStatus:
        Lightweight pairing of a step name with its coarse status for
        diagnostic and summarization purposes.

This module contains no policy logic, no hint generation, and no coupling to
file-type processors. It is intentionally pure and side-effect-free so that
status evaluation remains predictable, testable, and import-safe.
"""

from dataclasses import dataclass
from typing import TypedDict

from topmark.pipeline.hints import Axis
from topmark.pipeline.status import (
    BaseStatus,
    ComparisonStatus,
    ContentStatus,
    FsStatus,
    GenerationStatus,
    HeaderStatus,
    PatchStatus,
    PlanStatus,
    RenderStatus,
    ResolveStatus,
    StripStatus,
    WriteStatus,
)


class AxisStatusPayload(TypedDict):
    """Typed payload describing the status of a single pipeline axis.

    Keys:
        axis: Machine-friendly axis name (for example, "fs" or "header").
        name: Enum member name for the axis status (for example, "OK" or "MISSING").
        label: Human-readable label for the status, derived from the enum's
            ``.value``.
    """

    axis: str
    name: str
    label: str


@dataclass
class HeaderProcessingStatus:
    """Tracks the status of each processing phase for a single file.

    Each attribute corresponds to a pipeline axis and is represented by a
    dedicated status enum. This dataclass is the single source of truth for
    per-axis status in the pipeline.

    Attributes:
        resolve (ResolveStatus): Status of file-type resolution.
        fs (FsStatus): File system status (existence, permissions, binary guard).
        content (ContentStatus): Status of content-level checks (BOM, shebang,
            mixed newlines, readability).
        header (HeaderStatus): Status of header detection and parsing.
        generation (GenerationStatus): Status of header field/value generation.
        render (RenderStatus): Status of header rendering for the active file
            type.
        strip (StripStatus): Status of header stripping preparation and
            execution.
        comparison (ComparisonStatus): Status of comparing original vs. updated
            content.
        plan (PlanStatus): Status of planning updates prior to writing.
        patch (PatchStatus): Status of patch generation.
        write (WriteStatus): Status of writing changes back to the file system.
    """

    # File type resolution status:
    resolve: ResolveStatus = ResolveStatus.PENDING

    # File system status (existence, permissions, binary):
    fs: FsStatus = FsStatus.PENDING

    # File content status (BOM, shebang, mixed newlines, readability):
    content: ContentStatus = ContentStatus.PENDING

    # Header-level axes: detect existing header
    header: HeaderStatus = HeaderStatus.PENDING  # Status of header detection/parsing

    # A. Check -- insert / update headers
    # A.1 Generate updated header list and updated header value dict
    generation: GenerationStatus = GenerationStatus.PENDING  # Status of header dict generation

    # A.2 Render the updated header according to the file type and header processor
    render: RenderStatus = RenderStatus.PENDING  # Status of header rendering

    # B. Strip -- remove existing header
    strip: StripStatus = StripStatus.PENDING  # Status of header stripping lifecycle

    # Compare existing and updated file image
    comparison: ComparisonStatus = ComparisonStatus.PENDING  # Status of header comparison

    # Plan updates to the file
    plan: PlanStatus = PlanStatus.PENDING  # Status of file update (prior to writing)

    # Generate a patch for updated files
    patch: PatchStatus = PatchStatus.PENDING  # Status of patch generation

    # Write changes
    write: WriteStatus = WriteStatus.PENDING  # Status of writing the header

    def get(self, axis: Axis) -> BaseStatus:
        """Get the status for a given Axis.

        Args:
            axis (Axis): The Axis we want to get the status for;

        Returns:
            BaseStatus: The status for the given Axis.
        """
        match axis:
            case Axis.RESOLVE:
                return self.resolve
            case Axis.FS:
                return self.fs
            case Axis.CONTENT:
                return self.content
            case Axis.HEADER:
                return self.header
            case Axis.GENERATION:
                return self.generation
            case Axis.RENDER:
                return self.render
            case Axis.STRIP:
                return self.strip
            case Axis.COMPARISON:
                return self.comparison
            case Axis.PLAN:
                return self.plan
            case Axis.PATCH:
                return self.patch
            case Axis.WRITE:
                return self.write

    def reset(self) -> None:
        """Reset all status fields to ``PENDING``.

        This helper is mainly intended for tests or reuse of an existing
        ``HeaderProcessingStatus`` instance.

        Returns:
            None: The instance is mutated in place.
        """
        self.resolve = ResolveStatus.PENDING
        self.fs = FsStatus.PENDING
        self.content = ContentStatus.PENDING
        self.header = HeaderStatus.PENDING
        self.generation = GenerationStatus.PENDING
        self.render = RenderStatus.PENDING
        self.strip = StripStatus.PENDING
        self.comparison = ComparisonStatus.PENDING
        self.plan = PlanStatus.PENDING
        self.patch = PatchStatus.PENDING
        self.write = WriteStatus.PENDING

    def to_dict(self) -> dict[str, AxisStatusPayload]:
        """Return axis → {axis, name, label} payload for all axes.

        This mirrors ``AxisStatusPayload`` and is useful if you want a single,
        centralized representation of axis status data for machine output.

        Returns:
            dict[str, AxisStatusPayload]: Mapping from axis name to its status
            payload.
        """
        data: dict[str, AxisStatusPayload] = {}
        for axis in Axis:
            attr_name: str = axis.value  # e.g. "resolve"
            status: BaseStatus = getattr(self, attr_name)
            label: str = status.value  # ColoredStrEnum: (label, color)
            axis_name: str = axis.value
            data[axis_name] = {
                "axis": axis_name,
                "name": status.name,
                "label": label,
            }
        return data


@dataclass
class StepStatus:
    """Lightweight pairing of a step name with its coarse status.

    This structure is primarily used for diagnostics and summaries that need
    to report per-step outcomes.

    Attributes:
        step (str): Name of the pipeline step.
        status (BaseStatus): Coarse status for the step, typically derived
            from its primary axis.
    """

    step: str
    status: BaseStatus
