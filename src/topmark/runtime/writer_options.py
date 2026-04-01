# topmark:header:start
#
#   project      : TopMark
#   file         : writer_options.py
#   file_relpath : src/topmark/runtime/writer_options.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Persisted writer options loaded from TopMark TOML sources.

This module defines the non-layered writer preferences that may be authored in the
same TOML document as layered TopMark configuration. These options are resolved
separately from [`Config`][topmark.config.model.Config] and do not participate in
config-layer merging.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.config.types import FileWriteStrategy


@dataclass(frozen=True, slots=True)
class WriterOptions:
    """Persisted writer preferences parsed from TOML.

    Attributes:
        file_write_strategy: Preferred file write strategy declared in the
            `[writer]` table. `None` means that the TOML source does not
            specify a writer preference.
    """

    file_write_strategy: FileWriteStrategy | None = None
