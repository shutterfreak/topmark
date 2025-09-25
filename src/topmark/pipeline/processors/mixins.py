# topmark:header:start
#
#   project      : TopMark
#   file         : mixins.py
#   file_relpath : src/topmark/pipeline/processors/mixins.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Common mixins for header processors.

These mixins provide reusable behavior for:

* Line-comment based processors (e.g., Pound/Slash) via [`LineCommentMixin`][].
* Positional, tag- or prolog-sensitive processors (e.g., XML/HTML) via
  [`XmlPositionalMixin`][].
* Shebang-aware insertion rules via [`ShebangAwareMixin`][].

They **do not** change public behavior on their own. Processors can adopt these
mixins to share well-tested logic and reduce duplication.
"""

from __future__ import annotations

import re
from typing import Final, Sequence

_RE_SHEBANG: Final[re.Pattern[str]] = re.compile(r"^#!")
_RE_XML_DECL: Final[re.Pattern[str]] = re.compile(r"^\s*<\?xml\b", re.IGNORECASE)
_RE_DOCDECL: Final[re.Pattern[str]] = re.compile(r"^\s*<!DOCTYPE\b", re.IGNORECASE)
_RE_HTML_COMMENT_OPEN: Final[re.Pattern[str]] = re.compile(r"^\s*<!--")
_RE_BOM: Final[str] = "\ufeff"


class ShebangAwareMixin:
    """Utilities to skip shebang lines when inserting headers.

    Notes:
        These helpers operate on line-oriented content. Processors that manage
        character offsets should translate as needed (e.g., `splitlines(True)`).
    """

    def _skip_shebang(self, lines: Sequence[str]) -> int:
        """Return the insertion start index after an optional shebang.

        BOM handling is performed upstream in the reader step; this mixin does not
        attempt to normalize or validate BOM+shebang combinations.
        """
        i = 0
        if lines and _RE_SHEBANG.match(lines[0] or ""):
            i = 1
        return i


class LineCommentMixin(ShebangAwareMixin):
    """Shared helpers for line-comment based processors.

    Processors should define:
        * ``line_prefix``: the comment introducer for a header line (e.g., ``# ``).
        * ``line_suffix`` (optional): trailing comment portion to append (e.g., `` */``).

    Methods here centralize header line normalization, scanning, and safe
    insertion point computation (shebang aware).
    """

    #: Override per concrete processor, e.g., "# ", "// ", "; ", "-- "
    line_prefix: str = ""
    #: Optional suffix appended after content (rare for line comments)
    line_suffix: str = ""

    # ---- Line classification -------------------------------------------------

    def is_header_line(self, line: str) -> bool:
        """Return True if the line begins with the configured comment prefix."""
        return bool(self.line_prefix) and line.startswith(self.line_prefix)

    def strip_line_prefix(self, line: str) -> str:
        """Remove a single leading comment prefix; return original if absent."""
        if self.is_header_line(line):
            return line[len(self.line_prefix) :]
        return line

    def render_header_line(self, payload: str) -> str:
        """Render a header line with prefix (+ optional suffix).

        The caller is responsible for appending a newline when assembling
        multiple lines.
        """
        if self.line_suffix:
            return f"{self.line_prefix}{payload}{self.line_suffix}"
        return f"{self.line_prefix}{payload}"

    # ---- Insertion index helpers --------------------------------------------

    def find_insertion_index(self, lines: Sequence[str]) -> int:
        """Determine where a header should be inserted for line-comment files.

        Behavior:
            * If a FileTypeHeaderPolicy is attached to this processor's file type
              and explicitly sets ``supports_shebang=False``, do **not** skip a
              leading shebang even if present.
            * Otherwise, skip a leading shebang at line 0.
            * If the policy declares an ``encoding_line_regex``, and a shebang was
              skipped, also skip a single encoding line immediately following.
        """
        # Default: honor policy when present; otherwise use conservative defaults.
        policy = getattr(getattr(self, "file_type", None), "header_policy", None)

        # If the policy explicitly disables shebang support, do not skip it.
        if policy is not None and not getattr(policy, "supports_shebang", False):
            return 0

        # By default (or if supports_shebang=True), skip a leading shebang.
        i = self._skip_shebang(lines)

        # If an encoding regex is declared, skip a single encoding line after shebang.
        enc_re = getattr(policy, "encoding_line_regex", None) if policy is not None else None
        if i == 1 and enc_re:
            try:
                enc_pattern: re.Pattern[str] = re.compile(enc_re)
                if len(lines) > 1 and enc_pattern.search(lines[1]):
                    i = 2
            except re.error:
                # Invalid encoding regex should not break header insertion.
                pass

        return i


class XmlPositionalMixin:
    """Helpers for tag-sensitive (positional) processors like XML/HTML.

    This mixin offers small, composable predicates and insertion index logic
    that respect XML declarations and document type declarations (DOCTYPE).
    """

    # ---- Prolog / declaration predicates ------------------------------------

    def is_xml_declaration(self, line: str) -> bool:
        """Return True for an XML declaration line (``<?xml ...?>``)."""
        return bool(_RE_XML_DECL.match(line))

    def is_doctype_declaration(self, line: str) -> bool:
        """Return True for a DOCTYPE declaration line."""
        return bool(_RE_DOCDECL.match(line))

    def is_html_comment_open(self, line: str) -> bool:
        """Return True if the line opens an HTML/XML comment block."""
        return bool(_RE_HTML_COMMENT_OPEN.match(line))

    # ---- Insertion index helpers --------------------------------------------

    def find_xml_insertion_index(self, lines: Sequence[str]) -> int:
        """Return the line index after XML declaration and DOCTYPE (if present).

        Notes:
            BOM handling is performed upstream in the reader step; this helper
            assumes lines are already normalized. The check is purely line-based
            and does not attempt to coalesce declaration/content that share a
            single line (the XML processor's char-offset path covers that case).
        """
        i = 0
        if i < len(lines) and self.is_xml_declaration(lines[i]):
            i += 1
        if i < len(lines) and self.is_doctype_declaration(lines[i]):
            i += 1
        return i
