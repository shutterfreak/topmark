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
- Symbols exported by ``topmark.api`` via ``__all__`` are the supported surface.
- Adding optional parameters with defaults is allowed in minor releases.
- Removing/renaming symbols or changing return shapes is a breaking change.

High-level concepts:
- **Recognized** file types exist in the file type registry.
- **Supported** file types are recognized *and* have a processor bound.
- Diagnostics returned by the API are JSON-friendly and use string severities:
  ``"info"``, ``"warning"``, ``"error"``.

Configuration contract:
- Public pipeline functions (``check()``, ``strip()``) accept an optional plain mapping
  (mirroring the TOML/pyproject structure) or a frozen
  [`Config`][topmark.config.model.Config].
- Passing ``config=None`` triggers layered discovery (defaults → user → project) using the
  same rules as the CLI.
- The internal [`MutableConfig`][topmark.config.model.MutableConfig] builder is not part of
  the public API; it exists to perform discovery/merging and is frozen immediately before
  execution.

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
        }
    }

    run: api.runResult = api.check(
        ["src"],
        config=config,
        diff=True,
        skip_compliant=True,
    )

    assert run.summary.get("unchanged", 0) >= 0
```
"""

from __future__ import annotations

from topmark.api.commands.pipeline import check
from topmark.api.commands.pipeline import strip
from topmark.api.commands.registry import list_filetypes
from topmark.api.commands.registry import list_processors
from topmark.api.commands.version import get_version_info
from topmark.api.commands.version import get_version_text
from topmark.api.types import DiagnosticEntry
from topmark.api.types import FileResult
from topmark.api.types import FileTypeInfo
from topmark.api.types import Outcome
from topmark.api.types import ProcessorInfo
from topmark.api.types import RunResult
from topmark.version.types import VersionInfo

__all__ = (  # noqa: RUF022
    # Types
    "FileResult",
    "FileTypeInfo",
    "Outcome",
    "ProcessorInfo",
    "DiagnosticEntry",
    "RunResult",
    "VersionInfo",
    # Commands
    "check",
    "strip",
    "list_filetypes",
    "list_processors",
    "get_version_info",
    "get_version_text",
)
