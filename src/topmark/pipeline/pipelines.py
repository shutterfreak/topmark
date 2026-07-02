# topmark:header:start
#
#   project      : TopMark
#   file         : pipelines.py
#   file_relpath : src/topmark/pipeline/pipelines.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Named pipeline variants for TopMark (immutable, typed step sequences).

This module exposes immutable, typed step tuples and a registry mapping names
to pipelines. Pipelines are built from class-based steps that implement the
[`Step`][topmark.pipeline.protocols.Step] protocol.

Overview
--------
- ``PROBE``: probe resolution only
- ``SCAN``: resolve → sniff → read → scan
- ``CHECK_RENDER``: SCAN + build → render
- ``CHECK`` (summary): CHECK_RENDER + compare
- ``CHECK_*`` (apply/patch): CHECK + update → (patch/write) variants
- ``STRIP`` (summary): SCAN + strip → compare
- ``STRIP_*`` (apply/patch): STRIP + update → (patch/write) variants

Mermaid (orientation)
---------------------
```mermaid
flowchart TD

  subgraph Discovery
    P[prober]
    R[resolver]
    S[sniffer]
    D[reader]
    N[scanner]

    R --> S --> D --> N
  end

  subgraph Check
    B[builder]
    T[renderer]
    C[comparer]

    N --> B --> T --> C
  end

  subgraph Strip
    X[stripper]

    N --> X --> C
  end

  subgraph Mutations
    U[updater]
    H[patcher]
    W[writer]

    C --> U
    U -->|patch| H
    U -->|apply| W
  end
```

Notes:
* Pipelines are immutable (Final[tuple[Step, ...]]) and steps are
  instantiated objects (not functions).
* Steps only write to the status axes they declare; outcome classification is
  derived centrally at the view/API layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from typing import Final

from topmark.core.logging import get_logger
from topmark.pipeline.steps import builder
from topmark.pipeline.steps import comparer
from topmark.pipeline.steps import patcher
from topmark.pipeline.steps import planner
from topmark.pipeline.steps import prober
from topmark.pipeline.steps import reader
from topmark.pipeline.steps import renderer
from topmark.pipeline.steps import resolver
from topmark.pipeline.steps import scanner
from topmark.pipeline.steps import sniffer
from topmark.pipeline.steps import stripper
from topmark.pipeline.steps import writer

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.kinds import PipelineKindLiteral
    from topmark.pipeline.protocols import Step


logger: TopmarkLogger = get_logger(__name__)

__all__ = (
    "Pipeline",
    "PipelineDefinition",
    "PipelineSelection",
    "select_pipeline",
)

PROBE_PIPELINE: Final[tuple[Step[ProcessingContext], ...]] = (
    prober.ProberStep(),  # Probe file type/processor resolution and halt.
)
"""Probe file type and header processor resolution for a given file."""

SCAN_PIPELINE: Final[tuple[Step[ProcessingContext], ...]] = (
    resolver.ResolverStep(),  # Resolve file type and assign header processor for the file
    sniffer.SnifferStep(),  # Cheap pre-read checks and newline policy
    reader.ReaderStep(),  # Read the file
    scanner.ScannerStep(),  # Scan the file for a header
)
"""Perform basic TopMark header scanning."""

CHECK_RENDER_PIPELINE: Final[tuple[Step[ProcessingContext], ...]] = SCAN_PIPELINE + (
    builder.BuilderStep(),  # Build the dict with expected header fields
    renderer.RendererStep(),  # Render the updated header
)
"""Render-only pipeline: resolves, sniffs, reads, scans, builds, and renders
(no compare/update/patch)."""

CHECK_SUMMMARY_PIPELINE: Final[tuple[Step[ProcessingContext], ...]] = CHECK_RENDER_PIPELINE + (
    comparer.ComparerStep(),  # Compare existing header with rendered new header
)
"""A lightweight pipeline that stops after comparison (no update/patch)."""

CHECK_PATCH_PIPELINE: Final[tuple[Step[ProcessingContext], ...]] = CHECK_SUMMMARY_PIPELINE + (
    planner.PlannerStep(),  # Update the file
    patcher.PatcherStep(),  # Generate unified diff (needs comparer.compare)
)
"""Only for generating unified diffs."""

CHECK_APPLY_PIPELINE: Final[tuple[Step[ProcessingContext], ...]] = CHECK_SUMMMARY_PIPELINE + (
    planner.PlannerStep(),  # Update the file
    writer.WriterStep(),  # Write changes to file/stdout
)


STRIP_PIPELINE: Final[tuple[Step[ProcessingContext], ...]] = SCAN_PIPELINE + (
    stripper.StripperStep(),  # Strip the header from the file
)
"""NOTE: we do not run ComparerStep in a strip pipeline."""

STRIP_PATCH_PIPELINE: Final[tuple[Step[ProcessingContext], ...]] = STRIP_PIPELINE + (
    comparer.ComparerStep(),  # Compare existing header with rendered stripped header
    planner.PlannerStep(),  # Update the file
    patcher.PatcherStep(),  # Generate unified diff (needs comparer.compare)
)
"""Only for generating unified diffs."""

STRIP_APPLY_PIPELINE: Final[tuple[Step[ProcessingContext], ...]] = STRIP_PIPELINE + (
    planner.PlannerStep(),  # Update the file
    writer.WriterStep(),  # Write changes to file/stdout
)


@dataclass(frozen=True, kw_only=True, slots=True)
class PipelineDefinition:
    """Concrete executable pipeline definition.

    Attributes:
        name: Stable internal variant name.
        family: High-level pipeline family represented by this variant, or
            `None` for reusable internal building blocks such as `scan`.
        steps: Concrete ordered step sequence for execution.
        mutates: Whether this variant can write file/stdout content.
        emits_patch: Whether this variant can emit unified-diff patch output.
    """

    name: str
    family: PipelineKindLiteral | None
    steps: tuple[Step[ProcessingContext], ...]
    mutates: bool = False
    emits_patch: bool = False


class Pipeline(str, Enum):
    """Available named pipeline variants for file processing.

    Enum values are stable internal variant identifiers. Rich execution metadata
    is provided by [`PipelineDefinition`][topmark.pipeline.pipelines.PipelineDefinition]
    through the [`definition`][topmark.pipeline.pipelines.Pipeline.definition]
    property.
    """

    PROBE = "probe"
    SCAN = "scan"
    CHECK_RENDER = "check-render"
    CHECK = "check"
    CHECK_APPLY = "check-apply"
    CHECK_PATCH = "check-patch"
    STRIP = "strip"
    STRIP_APPLY = "strip-apply"
    STRIP_PATCH = "strip-patch"

    @property
    def definition(self) -> PipelineDefinition:
        """Return the rich catalogue definition for this pipeline variant.

        Returns:
            The immutable pipeline definition registered for this variant.
        """
        return PIPELINE_DEFINITIONS[self]

    @property
    def steps(self) -> tuple[Step[ProcessingContext], ...]:
        """Return the instantiated, ordered step sequence for this pipeline.

        Returns:
            An immutable tuple of step instances that implement the
            [`Step`][topmark.pipeline.protocols.Step] protocol. The runner will
            invoke them as callables in order.
        """
        return self.definition.steps

    @property
    def family(self) -> PipelineKindLiteral | None:
        """Return the high-level invocation family for this variant, if any.

        Returns:
            The pipeline family, or `None` for internal reusable variants.
        """
        return self.definition.family

    @property
    def mutates(self) -> bool:
        """Return whether this pipeline variant can mutate content.

        Returns:
            True when the variant includes a writer step.
        """
        return self.definition.mutates

    @property
    def emits_patch(self) -> bool:
        """Return whether this pipeline variant can emit patch output.

        Returns:
            True when the variant includes a patcher step.
        """
        return self.definition.emits_patch


PIPELINE_DEFINITIONS: Final[dict[Pipeline, PipelineDefinition]] = {
    Pipeline.PROBE: PipelineDefinition(
        name=Pipeline.PROBE.value,
        family="probe",
        steps=PROBE_PIPELINE,
    ),
    Pipeline.SCAN: PipelineDefinition(
        name=Pipeline.SCAN.value,
        family=None,
        steps=SCAN_PIPELINE,
    ),
    Pipeline.CHECK_RENDER: PipelineDefinition(
        name=Pipeline.CHECK_RENDER.value,
        family="check",
        steps=CHECK_RENDER_PIPELINE,
    ),
    Pipeline.CHECK: PipelineDefinition(
        name=Pipeline.CHECK.value,
        family="check",
        steps=CHECK_SUMMMARY_PIPELINE,
    ),
    Pipeline.CHECK_APPLY: PipelineDefinition(
        name=Pipeline.CHECK_APPLY.value,
        family="check",
        steps=CHECK_APPLY_PIPELINE,
        mutates=True,
    ),
    Pipeline.CHECK_PATCH: PipelineDefinition(
        name=Pipeline.CHECK_PATCH.value,
        family="check",
        steps=CHECK_PATCH_PIPELINE,
        emits_patch=True,
    ),
    Pipeline.STRIP: PipelineDefinition(
        name=Pipeline.STRIP.value,
        family="strip",
        steps=STRIP_PIPELINE,
    ),
    Pipeline.STRIP_APPLY: PipelineDefinition(
        name=Pipeline.STRIP_APPLY.value,
        family="strip",
        steps=STRIP_APPLY_PIPELINE,
        mutates=True,
    ),
    Pipeline.STRIP_PATCH: PipelineDefinition(
        name=Pipeline.STRIP_PATCH.value,
        family="strip",
        steps=STRIP_PATCH_PIPELINE,
        emits_patch=True,
    ),
}
"""Catalogue of available named pipeline variants."""


@dataclass(frozen=True, kw_only=True, slots=True)
class PipelineSelection:
    """Concrete pipeline selected for a high-level invocation.

    Attributes:
        kind: High-level pipeline family requested by the caller.
        apply: Whether the invocation allows mutation. This is retained even
            when the selected kind ignores it, such as `probe`.
        diff: Whether the invocation requested patch/diff output. This is
            retained even when the selected kind ignores it, such as `probe`.
        definition: Concrete executable pipeline definition selected for this
            invocation.
    """

    kind: PipelineKindLiteral
    apply: bool
    diff: bool
    definition: PipelineDefinition

    def __post_init__(self) -> None:
        """Validate that the selected definition matches the invocation family.

        Raises:
            ValueError: If the selected definition declares a different concrete
                pipeline family than the requested invocation kind.
        """
        if self.definition.family is None:
            return
        if self.definition.family != self.kind:
            msg: str = (
                "Pipeline definition family does not match selection kind: "
                f"{self.definition.family!r} != {self.kind!r}"
            )
            raise ValueError(msg)

    @property
    def steps(self) -> tuple[Step[ProcessingContext], ...]:
        """Return the immutable step sequence for the selected pipeline.

        Returns:
            Concrete ordered pipeline steps ready for execution by the pipeline
            engine.
        """
        return self.definition.steps


def select_pipeline(
    kind: PipelineKindLiteral,
    *,
    apply: bool,
    diff: bool,
) -> PipelineSelection:
    """Select a concrete pipeline variant for the requested invocation.

    Args:
        kind: Pipeline family to use: `"probe"`, `"check"`, or `"strip"`.
        apply: Whether to choose a mutating variant for pipeline families that
            support mutation. Ignored for `"probe"`, which is always read-only.
        diff: Whether to choose a patch-producing variant for pipeline families
            that support diffs. Ignored for `"probe"`, which does not produce
            content diffs.

    Returns:
        The selected concrete pipeline variant together with the invocation
        flags that led to the selection.

    Raises:
        RuntimeError: If an invalid pipeline kind was specified.
    """
    pipeline: Pipeline
    match kind:
        case "check":
            if apply:  # Mutate files
                pipeline = Pipeline.CHECK_APPLY
            else:  # Dry-run
                pipeline = Pipeline.CHECK_PATCH if diff else Pipeline.CHECK

        case "strip":
            if apply:  # Mutate files
                pipeline = Pipeline.STRIP_APPLY
            else:  # Dry-run
                pipeline = Pipeline.STRIP_PATCH if diff else Pipeline.STRIP

        case "probe":
            # Probe has a single diagnostic pipeline. It never writes files and
            # does not have patch/apply variants.
            pipeline = Pipeline.PROBE

        case _:
            # Defensive guard:
            raise RuntimeError(f"Invalid pipeline kind specified: {kind}")

    selection = PipelineSelection(
        kind=kind,
        apply=apply,
        diff=diff,
        definition=pipeline.definition,
    )
    logger.info("Selected pipeline: %s", selection.definition.name)
    return selection
