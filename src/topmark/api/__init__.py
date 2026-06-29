# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/api/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public TopMark API (stable surface).

This package provides a **small, typed façade** for running TopMark programmatically.

Design goals:
- Provide a stable entry point for integrations without requiring the CLI (Click).
- Keep inputs JSON/TOML-friendly (plain mappings) while maintaining strict internal typing.
- Return **machine-friendly** results (dataclasses / TypedDicts) without ANSI formatting.

Stability policy:
- Symbols exported by ``topmark.api`` via ``__all__`` are the supported surface,
  including stable re-exports such as [`Outcome`][topmark.core.outcomes.Outcome].
- Adding optional parameters with defaults is allowed in minor releases.
- Removing/renaming symbols or changing return shapes is a breaking change.
- Low-level runtime helpers may expose [`ApiPipelineRun`][topmark.api.types.ApiPipelineRun]
  when callers need resolved config, selected files, processing contexts, and a
  fatal pipeline-level exit code before conversion into public result DTOs.

High-level concepts:
- **Recognized** file types exist in the file type registry.
- **Supported** file types are recognized *and* have a processor bound.
- Diagnostics returned by the API are JSON-friendly and use string severities:
  ``"info"``, ``"warning"``, ``"error"``.
- Pipeline outcome values are shared core primitives re-exported here as
  [`Outcome`][topmark.core.outcomes.Outcome] for public API convenience.
- High-level commands return stable result DTOs such as
  [`RunResult`][topmark.api.types.RunResult] and
  [`ProbeRunResult`][topmark.api.types.ProbeRunResult]. Public streaming event
  DTOs such as [`ContentStreamEvent`][topmark.api.types.ContentStreamEvent],
  [`ProbeStreamEvent`][topmark.api.types.ProbeStreamEvent], and
  [`PublicStreamEvent`][topmark.api.types.PublicStreamEvent] define the
  compatibility surface for future incremental entry points without changing
  the current batch-oriented command behavior. Lower-level runtime
  orchestration returns [`ApiPipelineRun`][topmark.api.types.ApiPipelineRun]
  for integrations that intentionally work with processing contexts.

Configuration contract:
- Public pipeline functions (``probe()``, ``check()``, ``strip()``) accept an optional plain mapping
  (mirroring the TOML/pyproject structure) or an immutable
  [`FrozenConfig`][topmark.config.model.FrozenConfig].
- Passing ``config=None`` triggers layered discovery (defaults → user → project) using the
  same rules as the CLI.
- The internal [`MutableConfig`][topmark.config.model.MutableConfig] builder is not part of
  the public API; it exists to perform discovery/merging and is frozen immediately into an immutable
  [`FrozenConfig`][topmark.config.model.FrozenConfig] before execution.

Example:
    ```python
    from topmark import api

    config = {
        "fields": {
            "project": "TopMark",
            "license": "MIT",
        },
        "header": {
            "fields": [
                "file",
                "project",
                "license",
            ]
        },
        "formatting": {
            "align_fields": True,
        },
        "files": {
            "include_file_types": ["python"],
            "exclude_patterns": [".venv"],
        },
        "policy_by_type": {
            "python": {
                "allow_header_in_empty_files": True,
            },
        },
    }

    run: api.RunResult = api.check(
        ["src"],
        config=config,
        diff=True,
        report="actionable",
    )

    assert run.summary.get("unchanged", 0) >= 0
    ```
"""

from __future__ import annotations

from topmark.api.commands.pipeline import check
from topmark.api.commands.pipeline import probe
from topmark.api.commands.pipeline import strip
from topmark.api.commands.registry import list_filetypes
from topmark.api.commands.registry import list_processors
from topmark.api.commands.version import get_version_info
from topmark.api.commands.version import get_version_text
from topmark.api.types import ApiPipelineRun
from topmark.api.types import ContentStreamEvent
from topmark.api.types import DiagnosticEntry
from topmark.api.types import FileResult
from topmark.api.types import FileResultEvent
from topmark.api.types import FileTypeInfo
from topmark.api.types import ProbeCandidateInfo
from topmark.api.types import ProbeFileResult
from topmark.api.types import ProbeFileResultEvent
from topmark.api.types import ProbeRunResult
from topmark.api.types import ProbeStreamEvent
from topmark.api.types import ProcessorInfo
from topmark.api.types import PublicStreamEvent
from topmark.api.types import RunCompletedEvent
from topmark.api.types import RunResult
from topmark.api.types import RunStartedEvent
from topmark.core.outcomes import Outcome
from topmark.version.types import VersionInfo

__all__ = (
    "ApiPipelineRun",
    "ContentStreamEvent",
    "DiagnosticEntry",
    "FileResult",
    "FileResultEvent",
    "FileTypeInfo",
    "Outcome",
    "ProbeCandidateInfo",
    "ProbeFileResult",
    "ProbeFileResultEvent",
    "ProbeRunResult",
    "ProbeStreamEvent",
    "ProcessorInfo",
    "PublicStreamEvent",
    "RunCompletedEvent",
    "RunResult",
    "RunStartedEvent",
    "VersionInfo",
    "check",
    "get_version_info",
    "get_version_text",
    "list_filetypes",
    "list_processors",
    "probe",
    "strip",
)
