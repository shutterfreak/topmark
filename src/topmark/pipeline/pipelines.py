# topmark:header:start
#
#   file         : pipelines.py
#   file_relpath : src/topmark/pipeline/pipelines.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Named pipeline variants for TopMark.

This module exposes immutable, typed step sequences and a registry mapping names
to pipelines. The default set targets the "check" workflow; additional variants
are safe to add here (e.g., 'summary', 'apply').
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Mapping, Tuple

from topmark.pipeline.steps import stripper

from .steps import (
    builder,
    comparer,
    patcher,
    reader,
    renderer,
    resolver,
    scanner,
    updater,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.pipeline.contracts import Step

# Default pipeline used by the "check" command:
# resolve → read → scan → build → render → compare → update → patch
DEFAULT_PIPELINE: Final[Tuple[Step, ...]] = (
    resolver.resolve,  # Resolve file type and assign header processor for the file
    reader.read,  # Read the file
    scanner.scan,  # Scan the file for a header
    builder.build,  # Build the dict with expected header fields
    renderer.render,  # Render the updated header
    comparer.compare,  # Compare existing header with rendered new header
    updater.update,  # Update the file
    patcher.patch,  # Create a patch for patching the file
)

# A lighter-weight pipeline that stops after comparison (no update/patch)
SUMMARY_PIPELINE: Final[Tuple[Step, ...]] = (
    resolver.resolve,
    reader.read,
    scanner.scan,
    builder.build,
    renderer.render,
    comparer.compare,
)

# Render-only pipeline: resolves, reads, scans, builds, and renders (no compare/update/patch)
RENDER_PIPELINE: Final[Tuple[Step, ...]] = (
    resolver.resolve,
    reader.read,
    scanner.scan,
    builder.build,
    renderer.render,
)

# Apply pipeline: for now identical to DEFAULT (update + patch)
# When a dedicated writer step is introduced, extend this pipeline accordingly.
APPLY_PIPELINE: Final[Tuple[Step, ...]] = DEFAULT_PIPELINE

STRIP_PIPELINE: Final[Tuple[Step, ...]] = (
    resolver.resolve,
    reader.read,
    scanner.scan,
    stripper.strip,
    comparer.compare,
    updater.update,
    patcher.patch,  # Only needed with --diff
)

PIPELINES: Final[Mapping[str, Tuple[Step, ...]]] = {
    "default": DEFAULT_PIPELINE,
    "check": DEFAULT_PIPELINE,  # alias for ergonomics
    "summary": SUMMARY_PIPELINE,
    "render": RENDER_PIPELINE,
    "apply": APPLY_PIPELINE,
    "strip": STRIP_PIPELINE,
}


def get_pipeline(name: str) -> Sequence[Step]:
    """Return a pipeline by name, falling back to 'default' if unknown.

    Args:
      name: Pipeline name (e.g., 'default', 'check', 'summary').

    Returns:
      An immutable sequence of Step callables.

    Notes:
      The return type is a Sequence for flexibility at call sites while
      preserving immutability internally.
    """
    return PIPELINES.get(name, DEFAULT_PIPELINE)
