# topmark:header:start
#
#   project      : TopMark
#   file         : xml.py
#   file_relpath : src/topmark/pipeline/processors/xml.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Processor for files with HTML/XML-style block comments (<!-- ... -->).

This processor supports files using `<!-- ... -->`-style comments, such as MarkDown.
It delegates header processing to the core pipeline dispatcher.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.filetypes.registry import register_filetype
from topmark.pipeline.policy_whitespace import is_pure_spacer
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.processors.mixins import BlockCommentMixin, XmlPositionalMixin

if TYPE_CHECKING:
    from topmark.filetypes.policy import FileTypeHeaderPolicy

logger: TopmarkLogger = get_logger(__name__)


@register_filetype("html")
@register_filetype("markdown")
@register_filetype("svelte")
@register_filetype("svg")
@register_filetype("vue")
@register_filetype("xhtml")
@register_filetype("xml")
@register_filetype("xsl")
@register_filetype("xslt")
class XmlHeaderProcessor(XmlPositionalMixin, BlockCommentMixin, HeaderProcessor):
    """Header processor for XML/HTML-like formats (uses XmlPositionalMixin).

    This processor uses the **character-offset** strategy for placement:
    `get_header_insertion_index()` returns `NO_LINE_ANCHOR` and
    `get_header_insertion_char_offset()` computes the insertion offset. The
    pipeline falls back to line-based insertion only when no offset is returned.

    It still leverages the base processor for rendering, whitespace alignment,
    and policy-aware behavior where applicable.
    """

    def __init__(self) -> None:
        super().__init__(
            block_prefix="<!--",
            block_suffix="-->",
        )

    # XML/HTML processor uses a char-offset insertion strategy;
    # line-based helper is intentionally not used.
    def get_header_insertion_index(self, file_lines: list[str]) -> int:
        """Not used: return NO_LINE_ANCHOR.

        Rely solely on get_header_insertion_char_offset().

        Args:
            file_lines (list[str]): File content split into lines (unused).

        Returns:
            int: ``NO_LINE_ANCHOR`` to signal char-offset insertion.
        """
        from .base import NO_LINE_ANCHOR

        return NO_LINE_ANCHOR

    def get_header_insertion_char_offset(self, original_text: str) -> int | None:
        """Return a char offset to insert the header for XML/HTML-like documents.

        Handles optional BOM, XML declaration, optional DOCTYPE (including simple
        internal subsets), and consumes whitespace after the prolog if present. Works
        even when the root element follows on the same line.

        Args:
            original_text (str): Full file content as a single string.

        Returns:
            int | None: Character offset suitable for insertion, or ``None`` to use the
                line-based strategy.
        """
        text: str = original_text
        logger.debug(
            "xml.insert.char: begin; len=%d; head=%r", len(original_text), original_text[:40]
        )

        if not text:
            return 0

        offset: int = 0
        # UTF-8 BOM
        if text.startswith("\ufeff"):
            offset += 1

        # Leading ASCII whitespace
        m: re.Match[str] | None = re.match(r"[\t \r\n]*", text[offset:])
        if m:
            offset += m.end()

        # XML declaration
        if text[offset : offset + 5] == "<?xml":
            end_decl: int = text.find("?>", offset)
            if end_decl == -1:
                logger.warning(
                    "xml.insert.char: malformed decl; i=%d; head=%r", offset, original_text[:40]
                )
                return offset  # malformed; be conservative
            offset = end_decl + 2
            # Whitespace after declaration
            m = re.match(r"[\t \r\n]*", text[offset:])
            if m:
                offset += m.end()
            # Optional DOCTYPE (best-effort: up to next '>')
            if text[offset : offset + 9].upper() == "<!DOCTYPE":
                end_doc: int = text.find(">", offset)
                if end_doc != -1:
                    offset = end_doc + 1
                m = re.match(r"[\t \r\n]*", text[offset:])
                if m:
                    offset += m.end()

        # Return current offset; padding handled in prepare_header_for_insertion_text
        logger.debug(
            "xml.get_header_insertion_char_offset: returning offset %d; original_text[:40]: [%r]",
            offset,
            original_text[:40],
        )
        if "<?xml" in original_text and offset < original_text.find("<?xml"):
            logger.warning(
                "xml.insert.char: offset before first decl!? off=%d idx(%s)=%d",
                offset,
                "<?xml",
                original_text.find("<?xml"),
            )

        return offset

    def prepare_header_for_insertion_text(
        self,
        *,
        original_text: str,
        insert_offset: int,
        rendered_header_text: str,
        newline_style: str,
    ) -> str:
        """Adjust whitespace so the header block sits on its own lines.

        Policy: for XML-like formats we *always* want a leading blank after the
        prolog/doctype when inserting after it; by default we also want a
        trailing blank before body content. Trailing can be disabled explicitly
        via policy.ensure_blank_after_header = False.

        Args:
            original_text (str): Full file content as a single string.
            insert_offset (int): 0-based character offset where the header will be inserted.
            rendered_header_text (str): Header block text (may already include newlines).
            newline_style (str): Newline style (``LF``, ``CR``, ``CRLF``).

        Returns:
            str: Possibly modified header text to splice at ``insert_offset``.
        """
        logger.debug(
            "xml.insert.char.pad: offset=%d; before_tail=%r after_head=%r",
            insert_offset,
            original_text[max(0, insert_offset - 10) : insert_offset],
            original_text[insert_offset : insert_offset + 10],
        )
        policy: FileTypeHeaderPolicy | None = getattr(
            getattr(self, "file_type", None), "header_policy", None
        )
        # Policy: for XML-like formats we *always* want a leading blank after the
        # prolog/doctype when inserting after it; by default we also want a
        # trailing blank before body content. Trailing can be disabled explicitly
        # via policy.ensure_blank_after_header = False.
        want_trailing: bool = True
        if policy is not None and hasattr(policy, "ensure_blank_after_header"):
            want_trailing = policy.ensure_blank_after_header

        # Ensure the rendered block itself ends with exactly one newline
        block: str = rendered_header_text
        if not (block.endswith("\n") or block.endswith("\r\n")):
            block = block + newline_style

        # Determine if the char immediately before insert_offset is an EOL
        prev_char_is_eol: bool = False

        # --- Leading padding (after prolog/doctype, always for XML-like) ---
        # Add a single blank line *only* when inserting after a prolog/doctype and
        # the previous logical line is not already a policy-blank.
        add_leading_blank: bool = False
        if insert_offset > 0:
            # Determine previous logical line boundaries (CRLF-safe)
            i: int = insert_offset - 1
            # back up one if we are on LF of a CRLF pair
            if i > 0 and original_text[i] == "\n" and original_text[i - 1] == "\r":
                i -= 1
            # find start-of-line
            sol: int = i
            while sol > 0 and original_text[sol - 1] not in ("\n", "\r"):
                sol -= 1
            prev_line: str = original_text[sol : i + 1]

            # Heuristic: consider "after_prolog" when the previous line *is* a decl/doctype
            # (trim EOLs for matching). We do not rely on a sliding window substring test.
            prev_line_stripped: str = prev_line.rstrip("\r\n")

            # after_prolog: bool = prev_line_stripped.startswith(
            #     "<?xml"
            # ) or prev_line_stripped.upper().startswith("<!DOCTYPE")

            # after prev_line_stripped is computed:
            after_prolog: bool = prev_line_stripped.startswith(
                "<?xml"
            ) or prev_line_stripped.upper().startswith("<!DOCTYPE")
            if not after_prolog and prev_line_stripped.endswith(">"):
                # look back up to 3 lines above for a DOCTYPE opener
                scan_sol = sol
                look_back = 0
                while scan_sol > 0 and look_back < 3:
                    # jump to previous line start
                    scan_sol -= 1
                    while scan_sol > 0 and original_text[scan_sol - 1] not in ("\n", "\r"):
                        scan_sol -= 1
                    lb_line = original_text[scan_sol:sol].rstrip("\r\n")
                    if lb_line.upper().startswith("<!DOCTYPE"):
                        after_prolog = True
                        break
                    # prepare next iteration
                    sol = scan_sol
                    look_back += 1

            # Determine if the char immediately before insert_offset is an EOL

            if insert_offset > 0:
                c: str = original_text[insert_offset - 1]
                if c in ("\n", "\r"):
                    prev_char_is_eol = True
                elif insert_offset >= 2 and original_text[insert_offset - 2] == "\r" and c == "\n":
                    # CRLF pair: treat as EOL
                    prev_char_is_eol = True

            if after_prolog and not is_pure_spacer(prev_line, policy):
                add_leading_blank = True

        if add_leading_blank:
            # If we are splitting a single physical line (prolog + root on one line),
            # we need two newlines: one to end the prolog line and one blank line.
            # If the prolog already ended with an EOL, we only need one blank line.
            if not prev_char_is_eol:
                block = (newline_style * 2) + block
            else:
                block = newline_style + block

        # --- Trailing padding (policy-aware, idempotent) --------------------
        # Add a single blank line *only* when body content follows and the next slice
        # up to the next EOL is not a policy-blank.
        if want_trailing and insert_offset < len(original_text):
            # Determine end-of-line from insert_offset (CRLF-safe)
            j: int = insert_offset
            n: int = len(original_text)
            while j < n and original_text[j] not in ("\n", "\r"):
                j += 1
            next_slice: str = original_text[insert_offset:j]
            if not is_pure_spacer(next_slice, policy):
                block = block + newline_style
        # else: at EOF → no spacer

        logger.debug(
            "xml.insert.char.pad: block_head[:40]=%r block_tail[:40]=%r",
            block[:40],
            block[-40:],
        )

        return block

    def prepare_header_for_insertion(
        self,
        *,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
        newline_style: str,
    ) -> list[str]:
        """Ensure sensible padding around the header for HTML/XML-like files.

        - If inserting at index 0: no leading blank; ensure at least one trailing blank
          unless the next line is already blank/EOF.
        - If inserting after a prolog (index > 0): ensure exactly one leading blank
          (by checking the previous line), and ensure at least one trailing blank.

        Args:
            original_lines (list[str]): Original file lines.
            insert_index (int): Line index where the header will be inserted.
            rendered_header_lines (list[str]): Header lines to insert.
            newline_style (str): Newline style (``LF``, ``CR``, ``CRLF``).

        Returns:
            list[str]: Possibly modified header lines including any added padding.
        """
        out: list[str] = list(rendered_header_lines)

        # Policy: for XML-like formats we *always* want a leading blank after the
        # prolog/doctype when inserting after it; by default we also want a
        # trailing blank before body content. Trailing can be disabled explicitly
        # via policy.ensure_blank_after_header = False.
        policy: FileTypeHeaderPolicy | None = getattr(
            getattr(self, "file_type", None), "header_policy", None
        )
        # Default: want a blank before body content; tests expect this for XML/HTML-like
        want_trailing: bool = True
        if policy is not None and hasattr(policy, "ensure_blank_after_header"):
            want_trailing = bool(policy.ensure_blank_after_header)

        # ---- Leading padding (after prolog/doctype) ------------------------
        add_leading_blank: bool = False
        if insert_index > 0:
            # Previous logical line
            prev_line: str = (
                original_lines[insert_index - 1] if (insert_index - 1) < len(original_lines) else ""
            )
            prev_is_blank: bool = is_pure_spacer(prev_line, policy)

            # Detect insertion right after a prolog/doctype. Handle multi-line DOCTYPE
            # where the previous line is the tail (e.g., "]>").
            prev_line_stripped: str = prev_line.rstrip("\r\n")
            after_prolog: bool = prev_line_stripped.lstrip("\ufeff \t").startswith(
                "<?xml"
            ) or prev_line_stripped.lstrip().upper().startswith("<!DOCTYPE")
            if not after_prolog and prev_line_stripped.endswith(">"):
                # Look back up to 3 lines for a DOCTYPE opener
                back = 1
                i = insert_index - 2
                while back <= 3 and i >= 0 and not after_prolog:
                    cand = original_lines[i].rstrip("\r\n")
                    if cand.lstrip().upper().startswith("<!DOCTYPE"):
                        after_prolog = True
                        break
                    i -= 1
                    back += 1

            if after_prolog and not prev_is_blank:
                add_leading_blank = True

        if add_leading_blank:
            out = [newline_style] + out

        # ---- Trailing padding (before body) --------------------------------
        if want_trailing:
            has_next: bool = insert_index < len(original_lines)
            if has_next:
                next_line: str = original_lines[insert_index]
                if not is_pure_spacer(next_line, policy):
                    out = out + [newline_style]
            # If no body follows (EOF), do not add a trailing spacer.

        return out

    def validate_header_location(
        self,
        lines: list[str],
        *,
        header_start_idx: int,
        header_end_idx: int,
        anchor_idx: int,
    ) -> bool:
        """Validate the location of a detected header for XML/HTML-like files.

        Applies base proximity rules and a Markdown-specific safeguard to reject
        headers that appear inside fenced code blocks.

        Args:
            lines (list[str]): Full file content split into lines.
            header_start_idx (int): 0-based index of the candidate header's first line.
            header_end_idx (int): 0-based index of the candidate header's last line (inclusive).
            anchor_idx (int): 0-based expected insertion line index.

        Returns:
            bool: ``True`` if the candidate is acceptable; ``False`` otherwise.
        """
        # First apply the base proximity rule
        if not super().validate_header_location(
            lines,
            header_start_idx=header_start_idx,
            header_end_idx=header_end_idx,
            anchor_idx=anchor_idx,
        ):
            return False

        # Additional guard for Markdown: ignore headers that appear inside fenced code blocks
        # (``` or ~~~). This keeps README examples from being treated as real headers.
        if getattr(self.file_type, "name", "").lower() == "markdown":
            if self._inside_code_fence(lines, header_start_idx):
                return False
        return True

    def _inside_code_fence(self, lines: list[str], idx: int) -> bool:
        """Return True if ``idx`` lies inside a Markdown fenced code block.

        Counts opening fence markers (`````
        or ``~~~``) up to and including ``idx``
        and considers the index inside a fence when the count is odd.

        Args:
            lines (list[str]): Full file content split into lines.
            idx (int): Zero-based line index to test.

        Returns:
            bool: ``True`` if inside a code fence; ``False`` otherwise.
        """
        import re as _re

        fence: re.Pattern[str] = _re.compile(r"^\s*(```|~~~)")
        open_count = 0
        for i in range(0, min(idx + 1, len(lines))):
            if fence.match(lines[i]):
                open_count += 1
        return (open_count % 2) == 1

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> tuple[list[str], tuple[int, int] | None]:
        """Remove the TopMark header with minimal, policy-aware cleanup.

        Strategy 1 (strict gate): malformed or unsafe XML never reaches here because
        the pre-insert checker will skip insertion. Therefore we keep removal simple
        and conservative:

        - Delegate removal to the base class (span-aware, policy bounds).
        - Do **not** modify the XML declaration, DOCTYPE, or attempt single-line
          rejoin of the prolog seam.
        - If a trailing *policy-blank* immediately follows the removed header and
          the policy requested a spacer (``ensure_blank_after_header=True``), remove
          **at most one** such spacer line to restore the pre-header adjacency.

        Args:
            lines (list[str]): Full file content split into lines (keepends=True).
            span (tuple[int, int] | None): Optional (start, end) indices of the
                header block to remove; if ``None``, the base class attempts auto-detect.
            newline_style (str): Newline style (``LF``, ``CR``, ``CRLF``).
            ends_with_newline (bool | None): Whether the original file ended with a
                newline; not used by this simplified implementation but kept for
                signature compatibility.

        Returns:
            tuple[list[str], tuple[int, int] | None]: A tuple containing:
                - The updated list of file lines with the header removed.
                - The (start, end) line indices (inclusive) of the removed block
                  in the original input.
        """
        # Delegate policy-aware detection and removal to the base implementation
        updated: list[str]
        removed_span: tuple[int, int] | None
        updated, removed_span = super().strip_header_block(
            lines=lines,
            span=span,
            newline_style=newline_style,
            ends_with_newline=ends_with_newline,
        )
        if removed_span is None:
            return updated, None

        policy: FileTypeHeaderPolicy | None = getattr(
            getattr(self, "file_type", None), "header_policy", None
        )

        # Remove *one* trailing spacer that we likely introduced after the header
        # (only when policy asked for it). Never touch pre-header blanks or the prolog.
        if policy and bool(getattr(policy, "ensure_blank_after_header", False)):
            start, _end = removed_span
            if 0 <= start < len(updated) and is_pure_spacer(updated[start], policy):
                del updated[start]

        return updated, removed_span
