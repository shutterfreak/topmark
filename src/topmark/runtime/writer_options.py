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
from dataclasses import replace
from typing import TYPE_CHECKING

from topmark.config.types import OutputTarget

if TYPE_CHECKING:
    from topmark.config.types import FileWriteStrategy
    from topmark.runtime.model import RunOptions


@dataclass(frozen=True, slots=True)
class WriterOptions:
    """Persisted writer preferences parsed from TOML.

    Attributes:
        file_write_strategy: Preferred file write strategy declared in the
            `[writer]` table. `None` means that the TOML source does not
            specify a writer preference.
    """

    file_write_strategy: FileWriteStrategy | None = None


def apply_resolved_writer_options(
    run_options: RunOptions,
    writer_options: WriterOptions | None,
) -> RunOptions:
    """Overlay resolved persisted writer preferences onto runtime options.

    Persisted writer preferences are applied only when the invocation has not
    already selected a conflicting execution-only output mode.

    Precedence:
        1. explicit runtime output routing (for example STDOUT)
        2. explicit runtime file write strategy
        3. resolved TOML writer preference
        4. otherwise keep the original runtime options unchanged

    Args:
        run_options: Execution-only runtime options for the current run.
        writer_options: Resolved persisted writer preferences, if any.

    Returns:
        Runtime options with the resolved writer preference applied when doing
        so does not conflict with explicit runtime intent.
    """
    if writer_options is None or writer_options.file_write_strategy is None:
        return run_options

    if run_options.apply_changes is not True:
        return run_options

    if run_options.stdin_mode or run_options.output_target == OutputTarget.STDOUT:
        return run_options

    if run_options.file_write_strategy is not None:
        return run_options

    return replace(
        run_options,
        output_target=OutputTarget.FILE,
        file_write_strategy=writer_options.file_write_strategy,
    )
