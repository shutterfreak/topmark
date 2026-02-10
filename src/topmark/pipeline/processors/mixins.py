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

* Line-comment based processors (e.g., Pound/Slash) via ``LineCommentMixin``.
* Positional, tag- or prolog-sensitive processors (e.g., XML/HTML) via
  ``XmlPositionalMixin``.
* Shebang-aware insertion rules via ``ShebangAwareMixin``.

They **do not** change public behavior on their own. Processors can adopt these
mixins to share well-tested logic and reduce duplication.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Final, cast

from topmark.pipeline.policy_whitespace import is_pure_spacer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.filetypes.policy import FileTypeHeaderPolicy

_RE_SHEBANG: Final[re.Pattern[str]] = re.compile(r"^#!")
_RE_XML_DECL: Final[re.Pattern[str]] = re.compile(r"^\s*<\?xml\b", re.IGNORECASE)
_RE_DOCDECL: Final[re.Pattern[str]] = re.compile(r"^\s*<!DOCTYPE\b", re.IGNORECASE)
_RE_HTML_COMMENT_OPEN: Final[re.Pattern[str]] = re.compile(r"^\s*<!--")
_RE_BOM: Final[str] = "\ufeff"


def _equals_affix_ignoring_space_tab(line: str, affix: str) -> bool:
    """Return True if `line` equals `affix` when ignoring only spaces/tabs and EOLs.

    This is not a blank-collapsing check. We intentionally do *not* use
    `str.strip()` because it removes all Unicode whitespace (e.g., form-feed),
    which should remain significant for affix equality.
    """
    s: str = line.rstrip("\r\n").strip(" \t")
    return s == (affix or "")


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
        policy: FileTypeHeaderPolicy | None = getattr(
            getattr(self, "file_type", None), "header_policy", None
        )

        # If the policy explicitly disables shebang support, do not skip it.
        if policy is not None and not getattr(policy, "supports_shebang", False):
            return 0

        # By default (or if supports_shebang=True), skip a leading shebang.
        i: int = self._skip_shebang(lines)

        # If an encoding regex is declared, skip a single encoding line after shebang.
        enc_re: str | None = (
            getattr(policy, "encoding_line_regex", None) if policy is not None else None
        )
        if i == 1 and enc_re:
            try:
                enc_pattern: re.Pattern[str] = re.compile(enc_re)
                if len(lines) > 1 and enc_pattern.search(lines[1]):
                    i = 2
            except re.error:
                # Invalid encoding regex should not break header insertion.
                pass

        return i

    # ---- Header padding -----------------------------------------------------
    def prepare_header_for_insertion(
        self,
        *,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
        newline_style: str,
    ) -> list[str]:
        r"""Apply context-aware padding around the header for line-comment styles.

        Design goals:
          - Preserve **user whitespace** verbatim. In particular, if the first body
            line is whitespace-only (e.g., ``" \\n"``), do **not** rewrite or
            collapse it to an exact blank.
          - Add at most one **exact** blank separator (``newline_style``) *that we own*
            after the header **only if** body content follows and the next line is
            not already an exact blank. Never add a spacer at EOF.

        Args:
            original_lines: Original file lines (keepends=True).
            insert_index: Line index where the header will be inserted.
            rendered_header_lines: Header lines to insert (keepends=True).
            newline_style: Newline style (``LF``, ``CR``, ``CRLF``).

        Returns:
            list[str]: Possibly modified header lines including any added padding.
        """
        out: list[str] = list(rendered_header_lines)

        # Read policy if present
        policy: FileTypeHeaderPolicy | None = getattr(
            getattr(self, "file_type", None), "header_policy", None
        )

        want_leading: int = 0
        want_trailing: bool = True
        if policy is not None:
            want_leading = max(0, int(getattr(policy, "pre_header_blank_after_block", 0)))
            want_trailing = bool(getattr(policy, "ensure_blank_after_header", True))

        # ---- Leading padding
        if insert_index > 0 and want_leading > 0:
            prev_is_blank: bool = (insert_index - 1) < len(original_lines) and is_pure_spacer(
                original_lines[insert_index - 1], policy
            )
            if not prev_is_blank:
                out = [newline_style] + out

        # ---- Trailing padding
        if want_trailing:
            has_next: bool = insert_index < len(original_lines)
            if has_next:
                nxt: str = original_lines[insert_index]
                # Trailing spacer: add exactly one **owned** blank iff body follows AND
                # the very next line is **not** already an exact blank **and** does not
                # begin with a newline-equivalent control (bare CR, NEL, LS, PS).
                # Never modify the user's next line even if it's whitespace-only.

                # Treat these as newline-equivalent sentinels at line start.
                _nl_sentinels: tuple[str, ...] = ("\r", "\x85", "\u2028", "\u2029")
                if nxt != newline_style and not (nxt and nxt[0] in _nl_sentinels):
                    out = out + [newline_style]
            # else: inserting at EOF → no body follows → no spacer

        return out


# ---------------------------------------------------------------------------
# BlockCommentMixin: helpers for block-comment based processors
# ---------------------------------------------------------------------------


class BlockCommentMixin:
    """Shared helpers for block-comment processors (e.g., CSS/JS C-style).

    Processors should define:
        * ``block_prefix``: the opening delimiter (e.g., ``/*`` or ``<!--``).
        * ``block_suffix``: the closing delimiter (e.g., ``*/`` or ``-->``).

    The helpers here are intentionally minimal; they can be expanded as we
    migrate concrete processors and spot duplication opportunities.
    """

    block_prefix: str = ""
    block_suffix: str = ""

    def is_block_prefix(self, line: str) -> bool:
        """Return True if line is block prefix, ignoring spaces/tabs and EOLs.

        Returns True if `line` equals the configured block prefix,
        ignoring only spaces/tabs and EOLs.

        Affix equality ignores incidental surrounding spaces;
        blank collapsing is not performed here. We intentionally do *not* use
        `str.strip()` because it removes all Unicode whitespace (e.g., form-feed),
        which should remain significant for affix equality.

        Args:
            line: The line to check.

        Returns:
            True if `line` equals the configured block prefix, else False.
        """
        return _equals_affix_ignoring_space_tab(line, self.block_prefix or "")

    def is_block_suffix(self, line: str) -> bool:
        """Return True if line is block suffix, ignoring spaces/tabs and EOLs.

        Returns True if `line` equals the configured block suffix,
        ignoring only spaces/tabs and EOLs.

        Affix equality ignores incidental surrounding spaces;
        blank collapsing is not performed here. We intentionally do *not* use
        `str.strip()` because it removes all Unicode whitespace (e.g., form-feed),
        which should remain significant for affix equality.

        Args:
            line: The line to check.

        Returns:
            True if `line` equals the configured block suffix, else False.
        """
        return _equals_affix_ignoring_space_tab(line, self.block_suffix or "")

    def render_block_line(self, payload: str) -> str:
        """Render a content line inside a block (identity for now)."""
        return payload

    def ensure_block_padding(self, rendered_lines: list[str], *, newline: str) -> list[str]:
        r"""Ensure the block text ends with a newline.

        Args:
            rendered_lines: Lines that compose the block (including delimiters).
            newline: Newline string to enforce at the end ("\n" or "\r\n").

        Returns:
            Possibly adjusted copy with a trailing newline present.
        """
        out: list[str] = list(rendered_lines)
        if not out:
            return out
        last: str = out[-1]
        if not (last.endswith("\n") or last.endswith("\r\n")):
            out[-1] = last + newline
        return out


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

    def compute_insertion_anchor(self, lines: list[str]) -> int:
        """Line-based fallback: place header after XML decl and DOCTYPE (if present)."""
        return self.find_xml_insertion_index(lines)

    def prepare_header_for_insertion_text(
        self,
        *,
        original_text: str,
        insert_offset: int,
        rendered_header_text: str,
        newline_style: str,
    ) -> str:
        """Adjust whitespace so the header block sits on its own lines.

        Blank detection here approximates the policy in a text (char-offset) path:
        - Leading spacer is added only when inserting after some preamble and the
          previous character is not already an EOL.
        - Trailing spacer is added only when body content follows **and** the next
          slice up to the next EOL is **not** a policy-blank (checked via
          ``is_pure_spacer`` on the slice).

        Args:
            original_text: Full file content as a single string.
            insert_offset: 0-based character offset where the header will be inserted.
            rendered_header_text: Header block text (may already include newlines).
            newline_style: Newline style (``LF``, ``CR``, ``CRLF``).

        Returns:
            Possibly modified header text to splice at ``insert_offset``.
        """
        policy: FileTypeHeaderPolicy | None = getattr(
            getattr(self, "file_type", None), "header_policy", None
        )
        if policy is None:
            want_leading: bool = True
            want_trailing: bool = False
        else:
            want_leading = policy.pre_header_blank_after_block > 0
            want_trailing = bool(policy.ensure_blank_after_header)

        out: str = rendered_header_text

        # Optional leading spacer only if inserting after some preamble and previous char
        # isn't already a newline
        if want_leading and insert_offset > 0:
            prev: str = original_text[insert_offset - 1]
            if prev not in ("\n", "\r"):
                out = newline_style + out

        # Trailing spacer only when body content follows and the next slice (up to EOL)
        # is not a policy-blank. For text mode we approximate a line by scanning to EOL.
        if want_trailing and insert_offset < len(original_text):
            j: int = insert_offset
            n: int = len(original_text)
            while j < n and original_text[j] not in ("\n", "\r"):
                j += 1
            next_slice: str = original_text[insert_offset:j]
            if not is_pure_spacer(
                next_slice,
                getattr(getattr(self, "file_type", None), "header_policy", None),
            ):
                out = out + newline_style

        return out

    def prepare_header_for_insertion(
        self,
        *,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
        newline_style: str,
    ) -> list[str]:
        """Ensure the block itself ends with a newline, no extra spacer at EOF.

        For XML/HTML-like processors that also support line-based insertion,
        we only guarantee the block terminates with the dominant newline; we do
        not add a trailing spacer when inserting at EOF (that’s handled by the
        text path or upstream policy).

        Notes:
            Blank detection is policy-aware (STRICT/UNICODE/NONE) via `is_pure_spacer`.

        Args:
            original_lines: Original file lines.
            insert_index: Line index where the header will be inserted.
            rendered_header_lines: Header lines to insert.
            newline_style: Newline style (``LF``, ``CR``, ``CRLF``).

        Returns:
            Possibly modified header lines including any added padding.
        """
        # Detect the dominant newline from existing lines, default to "\n"
        out: list[str] = list(rendered_header_lines)

        # If BlockCommentMixin is in the MRO, use its helper to ensure a final newline.
        ensure_block_padding = getattr(self, "ensure_block_padding", None)
        if callable(ensure_block_padding):
            out = cast("list[str]", cast("Any", ensure_block_padding)(out, newline=newline_style))

        return out
