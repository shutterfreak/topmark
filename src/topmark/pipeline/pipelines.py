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

from enum import Enum
from typing import Final

from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.protocols import Step
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

CHECK_APPLY_PATCH_PIPELINE: Final[tuple[Step[ProcessingContext], ...]] = CHECK_SUMMMARY_PIPELINE + (
    planner.PlannerStep(),  # Update the file
    patcher.PatcherStep(),  # Generate unified diff (needs comparer.compare)
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

STRIP_APPLY_PATCH_PIPELINE: Final[tuple[Step[ProcessingContext], ...]] = STRIP_PIPELINE + (
    comparer.ComparerStep(),  # Compare existing header with rendered stripped header
    planner.PlannerStep(),  # Update the file
    patcher.PatcherStep(),  # Generate unified diff (needs comparer.compare)
    writer.WriterStep(),  # Write changes to file/stdout
)


class Pipeline(tuple[Step[ProcessingContext], ...], Enum):
    """Available execution pipelines for file processing, mapped to their step sequences."""

    # Note: Enum members use underscores instead of hyphens for valid Python identifiers.

    PROBE = PROBE_PIPELINE

    SCAN = SCAN_PIPELINE
    CHECK_RENDER = CHECK_RENDER_PIPELINE

    # "check" maps to the summary pipeline in the current PIPELINES dict
    CHECK = CHECK_SUMMMARY_PIPELINE
    CHECK_APPLY = CHECK_APPLY_PIPELINE
    CHECK_APPLY_PATCH = CHECK_APPLY_PATCH_PIPELINE
    CHECK_PATCH = CHECK_PATCH_PIPELINE

    # "strip" maps to the summary pipeline in the current PIPELINES dict
    STRIP = STRIP_PIPELINE
    STRIP_APPLY = STRIP_APPLY_PIPELINE
    STRIP_APPLY_PATCH = STRIP_APPLY_PATCH_PIPELINE
    STRIP_PATCH = STRIP_PATCH_PIPELINE

    @property
    def steps(self) -> tuple[Step[ProcessingContext], ...]:
        """Return the instantiated, ordered step sequence for this pipeline.

        Returns:
            tuple[Step, ...]: An immutable tuple of step *instances* that
            implement the [`Step`][topmark.pipeline.protocols.Step] protocol. The
            runner will invoke them as callables in order.
        """
        return self.value
