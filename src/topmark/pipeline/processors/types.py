# topmark:header:start
#
#   project      : TopMark
#   file         : types.py
#   file_relpath : src/topmark/pipeline/processors/types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Type definitions for the pipeline processing layer.

This module provides structured type definitions, such as dataclass objects,
used to pass data between the pipeline's distinct phases. These types improve
the clarity and type safety of complex return values compared to using
bare tuples or dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class HeaderParseResult:
    """Result of parsing key-value fields from a header block.

    This dataclass provides a structured and type-safe alternative to
    a bare return tuple, ensuring that consuming code can access the
    parsed data and metrics by name. The initializer requires all arguments
    to be passed by keyword.

    Attributes:
        fields (dict[str, str]): Mapping of all successfully parsed header fields
            (key → value). Defaults to an empty dictionary.
        success_count (int): The number of header lines that were successfully
            parsed and added to the ``fields`` dictionary. Defaults to 0.
        error_count (int): The number of header lines that were malformed (e.g.,
            missing a colon, or having an empty field name). Defaults to 0.
    """

    fields: dict[str, str] = field(default_factory=lambda: {})
    success_count: int = 0
    error_count: int = 0
