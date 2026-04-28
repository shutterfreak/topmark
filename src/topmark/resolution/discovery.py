# topmark:header:start
#
#   project      : TopMark
#   file         : discovery.py
#   file_relpath : src/topmark/resolution/discovery.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Discovery-level probe results for explicit input selection.

This module contains small value objects used to explain why an explicitly
requested path did or did not reach file-type resolution. It intentionally stays
separate from [`topmark.resolution.probe`][topmark.resolution.probe], because a
path excluded during file discovery has no file-type candidates yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class FileSelectionStatus(str, Enum):
    """Machine-friendly status for explicit input selection.

    Attributes:
        SELECTED: The explicit input reached file-type probing.
        FILTERED: The explicit input was filtered before file-type probing.
        NOT_FOUND: The explicit input path does not exist.
    """

    SELECTED = "selected"
    FILTERED = "filtered"
    NOT_FOUND = "not_found"


class FileSelectionReason(str, Enum):
    """Machine-friendly reason for explicit input selection.

    Attributes:
        SELECTED: The explicit input was selected for file-type probing.
        EXCLUDED_BY_PATH_FILTER: The explicit input was excluded by path filters.
        EXCLUDED_BY_FILE_TYPE_FILTER: The explicit input was excluded by file-type filters.
        EXCLUDED_BY_DISCOVERY_FILTER: The explicit input was excluded by discovery filters before
            file-type probing.
        NOT_A_FILE: The explicit input exists but is not a regular file.
        NOT_FOUND: The explicit input path does not exist.
    """

    SELECTED = "selected"
    EXCLUDED_BY_PATH_FILTER = "excluded_by_path_filter"
    EXCLUDED_BY_FILE_TYPE_FILTER = "excluded_by_file_type_filter"
    EXCLUDED_BY_DISCOVERY_FILTER = "excluded_by_discovery_filter"
    NOT_A_FILE = "not_a_file"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class FileSelectionProbeResult:
    """Explain whether an explicitly requested path reached file-type probing.

    Attributes:
        path: Explicit input path being explained. This may be relative to the
            current working directory or to a `files_from` source base.
        status: Selection status for the explicit input path.
        reason: Machine-friendly reason for the selection status. Reasons are
            intentionally coarse for now; exact pattern/source attribution can be
            added later without changing the basic probe contract.
    """

    path: Path
    status: FileSelectionStatus
    reason: FileSelectionReason
