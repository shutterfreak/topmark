# topmark:header:start
#
#   project      : TopMark
#   file         : pipelines.py
#   file_relpath : src/topmark/pipeline/pipelines.py
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

from enum import Enum
from typing import TYPE_CHECKING, Final, Tuple

from .steps import (
    builder,
    comparer,
    patcher,
    reader,
    renderer,
    resolver,
    scanner,
    sniffer,
    stripper,
    updater,
    writer,
)

if TYPE_CHECKING:
    from topmark.pipeline.contracts import Step


# Perform basic TopMark header scanning:
SCAN_PIPELINE: Final[Tuple[Step, ...]] = (
    resolver.resolve,  # Resolve file type and assign header processor for the file
    sniffer.sniff,  # Cheap pre-read checks and newline policy
    reader.read,  # Read the file
    scanner.scan,  # Scan the file for a header
)

# Render-only pipeline: resolves, sniffs, reads, scans, builds, and renders
# (no compare/update/patch):
CHECK_RENDER_PIPELINE: Final[Tuple[Step, ...]] = SCAN_PIPELINE + (
    builder.build,  # Build the dict with expected header fields
    renderer.render,  # Render the updated header
)

# A lightweight pipeline that stops after comparison (no update/patch):
CHECK_SUMMMARY_PIPELINE: Final[Tuple[Step, ...]] = CHECK_RENDER_PIPELINE + (
    comparer.compare,  # Compare existing header with rendered new header
)

# Only for generating unified diffs:
CHECK_PATCH_PIPELINE: Final[Tuple[Step, ...]] = CHECK_SUMMMARY_PIPELINE + (
    updater.update,  # Update the file
    patcher.patch,  # Generate unified diff (needs comparer.compare)
)

CHECK_APPLY_PIPELINE: Final[Tuple[Step, ...]] = CHECK_SUMMMARY_PIPELINE + (
    updater.update,  # Update the file
    writer.write,  # Write changes to file/stdout
)

CHECK_APPLY_PATCH_PIPELINE: Final[Tuple[Step, ...]] = CHECK_SUMMMARY_PIPELINE + (
    updater.update,  # Update the file
    patcher.patch,  # Generate unified diff (needs comparer.compare)
    writer.write,  # Write changes to file/stdout
)

STRIP_PIPELINE: Final[Tuple[Step, ...]] = SCAN_PIPELINE + (
    stripper.strip,  # Strip the header from the file
)

STRIP_SUMMMARY_PIPELINE: Final[Tuple[Step, ...]] = STRIP_PIPELINE + (
    comparer.compare,  # Compare existing header with rendered new header
)

# Only for generating unified diffs:
STRIP_PATCH_PIPELINE: Final[Tuple[Step, ...]] = STRIP_SUMMMARY_PIPELINE + (
    updater.update,  # Update the file
    patcher.patch,  # Generate unified diff (needs comparer.compare)
)

STRIP_APPLY_PIPELINE: Final[Tuple[Step, ...]] = STRIP_SUMMMARY_PIPELINE + (
    updater.update,  # Update the file
    writer.write,  # Write changes to file/stdout
)
STRIP_APPLY_PATCH_PIPELINE: Final[Tuple[Step, ...]] = STRIP_SUMMMARY_PIPELINE + (
    updater.update,  # Update the file
    patcher.patch,  # Generate unified diff (needs comparer.compare)
    writer.write,  # Write changes to file/stdout
)


class Pipeline(Enum):
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
    def steps(self) -> Tuple[Step, ...]:
        """Returns the immutable sequence of steps for this pipeline."""
        # The value of an Enum member is the tuple assigned to it.
        return self.value
