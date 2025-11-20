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
    R[resolver] --> S[sniffer] --> D[reader] --> N[scanner]
  end
  subgraph Check
    N --> B[builder] --> T[renderer] --> C[comparer]
  end
  subgraph Strip
    N --> P[stripper] --> C
  end
  subgraph Mutations
    C --> U[updater]
    U -->|patch| H[patcher]
    U -->|apply| W[writer]
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

from topmark.pipeline.protocols import Step

from .steps import (
    builder,
    comparer,
    patcher,
    planner,
    reader,
    renderer,
    resolver,
    scanner,
    sniffer,
    stripper,
    writer,
)

# Perform basic TopMark header scanning:
SCAN_PIPELINE: Final[tuple[Step, ...]] = (
    resolver.ResolverStep(),  # Resolve file type and assign header processor for the file
    sniffer.SnifferStep(),  # Cheap pre-read checks and newline policy
    reader.ReaderStep(),  # Read the file
    scanner.ScannerStep(),  # Scan the file for a header
)

# Render-only pipeline: resolves, sniffs, reads, scans, builds, and renders
# (no compare/update/patch):
CHECK_RENDER_PIPELINE: Final[tuple[Step, ...]] = SCAN_PIPELINE + (
    builder.BuilderStep(),  # Build the dict with expected header fields
    renderer.RendererStep(),  # Render the updated header
)

# A lightweight pipeline that stops after comparison (no update/patch):
CHECK_SUMMMARY_PIPELINE: Final[tuple[Step, ...]] = CHECK_RENDER_PIPELINE + (
    comparer.ComparerStep(),  # Compare existing header with rendered new header
)

# Only for generating unified diffs:
CHECK_PATCH_PIPELINE: Final[tuple[Step, ...]] = CHECK_SUMMMARY_PIPELINE + (
    planner.PlannerStep(),  # Update the file
    patcher.PatcherStep(),  # Generate unified diff (needs comparer.compare)
)

CHECK_APPLY_PIPELINE: Final[tuple[Step, ...]] = CHECK_SUMMMARY_PIPELINE + (
    planner.PlannerStep(),  # Update the file
    writer.WriterStep(),  # Write changes to file/stdout
)

CHECK_APPLY_PATCH_PIPELINE: Final[tuple[Step, ...]] = CHECK_SUMMMARY_PIPELINE + (
    planner.PlannerStep(),  # Update the file
    patcher.PatcherStep(),  # Generate unified diff (needs comparer.compare)
    writer.WriterStep(),  # Write changes to file/stdout
)

STRIP_PIPELINE: Final[tuple[Step, ...]] = SCAN_PIPELINE + (
    stripper.StripperStep(),  # Strip the header from the file
)

STRIP_SUMMMARY_PIPELINE: Final[tuple[Step, ...]] = STRIP_PIPELINE + (
    comparer.ComparerStep(),  # Compare existing header with rendered new header
)

# Only for generating unified diffs:
STRIP_PATCH_PIPELINE: Final[tuple[Step, ...]] = STRIP_SUMMMARY_PIPELINE + (
    planner.PlannerStep(),  # Update the file
    patcher.PatcherStep(),  # Generate unified diff (needs comparer.compare)
)

STRIP_APPLY_PIPELINE: Final[tuple[Step, ...]] = STRIP_SUMMMARY_PIPELINE + (
    planner.PlannerStep(),  # Update the file
    writer.WriterStep(),  # Write changes to file/stdout
)
STRIP_APPLY_PATCH_PIPELINE: Final[tuple[Step, ...]] = STRIP_SUMMMARY_PIPELINE + (
    planner.PlannerStep(),  # Update the file
    patcher.PatcherStep(),  # Generate unified diff (needs comparer.compare)
    writer.WriterStep(),  # Write changes to file/stdout
)


class Pipeline(tuple[Step, ...], Enum):
    """Available execution pipelines for file processing, mapped to their step sequences."""

    # Note: Enum members use underscores instead of hyphens for valid Python identifiers.

    SCAN = SCAN_PIPELINE
    CHECK_RENDER = CHECK_RENDER_PIPELINE

    # "check" maps to the summary pipeline in the current PIPELINES dict
    CHECK = CHECK_SUMMMARY_PIPELINE
    CHECK_APPLY = CHECK_APPLY_PIPELINE
    CHECK_APPLY_PATCH = CHECK_APPLY_PATCH_PIPELINE
    CHECK_PATCH = CHECK_PATCH_PIPELINE

    # "strip" maps to the summary pipeline in the current PIPELINES dict
    STRIP = STRIP_SUMMMARY_PIPELINE
    STRIP_APPLY = STRIP_APPLY_PIPELINE
    STRIP_APPLY_PATCH = STRIP_APPLY_PATCH_PIPELINE
    STRIP_PATCH = STRIP_PATCH_PIPELINE

    @property
    def steps(self) -> tuple[Step, ...]:
        """Return the instantiated, ordered step sequence for this pipeline.

        Returns:
            tuple[Step, ...]: An immutable tuple of step *instances* that
            implement the [`Step`][topmark.pipeline.protocols.Step] protocol. The
            runner will invoke them as callables in order.
        """
        return self.value
