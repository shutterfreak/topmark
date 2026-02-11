# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/cli/emitters/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI rendering and emission helpers for TopMark.

This module contains helpers used by concrete CLI commands to *emit* output,
both human-readable and machine-readable, to a `ConsoleLike` instance.

Responsibilities are intentionally split as follows:

Human-oriented output (TEXT format):
- banners and section headers,
- per-file summary lines and guidance,
- colored diagnostics and hints,
- unified diffs,
- TOML blocks for config-related commands.

Machine-oriented output (JSON / NDJSON):
- thin CLI-level emitters that *print* already-serialized JSON/NDJSON strings
  or streams produced elsewhere,
- no data shaping, schema decisions, or serialization logic lives here.

Architecture overview for machine formats:
- [`topmark.core.machine`][topmark.core.machine]:
    shared machine-output schemas, keys, meta payloads, and low-level normalization utilities.
- [`topmark.config.machine`][topmark.config.machine]:
    machine payloads/shapes/serializers for configuration inspection and validation commands.
- [`topmark.pipeline.machine`][topmark.pipeline.machine]:
    machine payloads/shapes/serializers for processing results (`check`, `strip`).
- [`topmark.registry.machine`][topmark.registry.machine]:
    machine payloads/shapes/serializers for registry inspection commands
    (`filetypes`, `processors`).

This module deliberately does **not** define machine schemas or JSON/NDJSON
serialization logic. Its role is limited to selecting the appropriate serializer
based on CLI options and emitting the resulting text to the console.

All printing goes through `ConsoleLike` instances obtained via
[`topmark.cli.console_helpers.get_console_safely`][topmark.cli.console_helpers.get_console_safely].
keeping Click-style concerns isolated from core logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger


logger: TopmarkLogger = get_logger(__name__)
