# topmark:header:start
#
#   project      : TopMark
#   file         : schemas.py
#   file_relpath : src/topmark/core/machine/schemas.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output schema helpers shared across TopMark.

This module contains small, pure dataclasses used by machine-output payloads.
It is intentionally CLI/console-free.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CommandSummary:
    """Identifies the TopMark command context for a machine-output record.

    Attributes:
        command (str): Top-level command name (e.g. "config", "check", "strip").
        subcommand (str | None): Optional subcommand name (e.g. "check" under "config").
    """

    command: str
    subcommand: str | None = None
