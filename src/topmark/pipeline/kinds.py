# topmark:header:start
#
#   project      : TopMark
#   file         : kinds.py
#   file_relpath : src/topmark/pipeline/kinds.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pipeline-family identifiers shared across runtime layers.

This module defines lightweight pipeline-kind aliases that are consumed by
pipeline execution, runtime configuration, CLI commands, and API entry points.

The aliases live in a dedicated low-level module so they can be imported by
both runtime and public-facing layers without creating dependency cycles.
In particular, pipeline-kind definitions are intentionally separated from
`topmark.api.types` because pipeline execution and result-reduction code
must not depend on API-specific modules.

Pipeline kinds describe the high-level intent of a pipeline invocation
(`probe`, `check`, or `strip`). They do not describe a specific pipeline
implementation or step sequence.
"""

from __future__ import annotations

from typing import Literal
from typing import TypeAlias

__all__ = ("PipelineKindLiteral",)


PipelineKindLiteral: TypeAlias = Literal[
    "probe",
    "check",
    "strip",
]
"""Allowed pipeline-family identifiers.

These values describe the high-level processing intent selected by the user
and are propagated through runtime execution and durable result snapshots.
"""
