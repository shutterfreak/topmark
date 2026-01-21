# topmark:header:start
#
#   project      : TopMark
#   file         : policy.py
#   file_relpath : src/topmark/filetypes/policy.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""File-type header insertion/strip policies.

This module defines configuration primitives used by TopMark processors to
insert, replace, and strip project headers in a file-type aware manner.

It provides:
  * `BlankCollapseMode`: An enum describing how to classify and collapse
    *blank* lines around a header during insert/strip repairs.
  * `FileTypeHeaderPolicy`: A dataclass capturing per-type rules such as
    shebang handling, encoding line detection, spacing before/after the header,
    and blank-line collapsing behavior.

Key policies
------------
TopMark defers to per-type policy for whitespace and preamble handling:

* **Shebang & encoding lines**
  Processors can skip a leading POSIX shebang (e.g., ``#!/usr/bin/env python``)
  and an optional encoding declaration immediately after it when
  ``supports_shebang`` is ``True`` and ``encoding_line_regex`` matches.

* **Spacing before the header**
  ``pre_header_blank_after_block`` controls how many blank lines should be
  placed between a preamble block (shebang/encoding, or other format preface)
  and the header. The default is 1 for readability.

* **Spacing after the header**
  ``ensure_blank_after_header`` asks processors to add exactly one blank line
  after the header when body content follows, avoiding extra blanks at EOF.

* **Blank-line collapse semantics**
  ``blank_collapse_mode`` controls what counts as a *blank* line during
  insert/strip repairs:
    - ``STRICT``: only spaces, tabs, and EOL markers are blank; control
      characters (e.g., form-feed ``\\x0c``) are preserved.
    - ``UNICODE``: all Unicode whitespace is blank (akin to ``str.strip()``).
    - ``NONE``: do not collapse blank-like lines beyond what TopMark inserted.
  ``blank_collapse_extra`` allows opting in additional characters (e.g.,
  ``"\\x0c"``) to be treated as blank under the selected mode.

These policies are intentionally conservative by default to maintain
idempotence (insert → strip → insert) and preserve user-authored content.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from topmark.config.logging import get_logger

if TYPE_CHECKING:
    from topmark.config.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)


class BlankCollapseMode(str, Enum):
    r"""How to identify and collapse *blank* lines during header insert/strip repairs.

    Members:
        STRICT: Treat only spaces, tabs, and line terminators as blank; preserve
            control characters such as form-feed (``\\x0c``).
        UNICODE: Treat all Unicode whitespace as blank (similar to ``str.strip()``).
        NONE: Do not collapse blank-like lines beyond what TopMark must add/remove
            for the header itself.
    """

    STRICT = "strict"
    UNICODE = "unicode"
    NONE = "none"


@dataclass
class FileTypeHeaderPolicy:
    r"""Policy describing how headers should be inserted/removed for a file type.

    These attributes are optional; processors read them to adapt behavior without
    hard-coding language specifics. Defaults are conservative and aim to preserve
    user-authored whitespace while keeping round-trips stable.

    Attributes:
        supports_shebang (bool): Whether this file type commonly starts with a POSIX
            shebang (e.g., ``#!/usr/bin/env bash``). When ``True``, processors may
            skip a leading shebang during placement.
        encoding_line_regex (str | None): Optional regex (string) that matches an
            encoding declaration line *immediately after* a shebang (e.g., Python
            PEP 263). When provided and a shebang was skipped, a matching line is
            also skipped for placement.
        pre_header_blank_after_block (int): Number of blank lines to place between a
            preamble block (shebang/encoding or similar) and the header. Typically 1.
        ensure_blank_after_header (bool): Ensure exactly one blank line follows the
            header when body content follows. No extra blank is added at EOF.
        blank_collapse_mode (BlankCollapseMode): How to identify and collapse *blank*
            lines around the header during insert/strip repairs. See
            `BlankCollapseMode` for semantics. Defaults to ``STRICT``.
        blank_collapse_extra (str): Additional characters to treat as blank **in
            addition** to those covered by ``blank_collapse_mode``. For example,
            set to ``\"\\x0c\"`` to consider form-feed collapsible for a given type.
    """

    supports_shebang: bool = False
    encoding_line_regex: str | None = None

    pre_header_blank_after_block: int = 1
    ensure_blank_after_header: bool = True

    # How to identify and collapse “blank” lines around the header during insert/strip repairs.
    blank_collapse_mode: BlankCollapseMode = BlankCollapseMode.STRICT
    blank_collapse_extra: str = ""
