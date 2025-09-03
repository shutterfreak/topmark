# topmark:header:start
#
#   file         : xml.py
#   file_relpath : src/topmark/pipeline/processors/xml.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Processor for files with HTML/XML-style block comments (<!-- ... -->).

This processor supports files using `<!-- ... -->`-style comments, such as MarkDown.
It delegates header processing to the core pipeline dispatcher.
"""

import re

from topmark.file_resolver import detect_newline
from topmark.filetypes.registry import register_filetype
from topmark.pipeline.processors.base import (
    HeaderProcessor,
)


@register_filetype("html")
@register_filetype("markdown")
@register_filetype("svelte")
@register_filetype("svg")
@register_filetype("vue")
@register_filetype("xhtml")
@register_filetype("xml")
@register_filetype("xsl")
@register_filetype("xslt")
class XmlHeaderProcessor(HeaderProcessor):
    """Processor for files with HTML/XML-style block comments (<!-- ... -->).

    Supported families include HTML, Markdown (HTML comments), XML and common
    XML-derived formats, as well as component templates that accept HTML comments
    (e.g., .vue, .svelte).
    """

    def __init__(self) -> None:
        """Initialize a XmlHeaderProcessor instance."""
        super().__init__(
            block_prefix="<!--",
            block_suffix="-->",
        )

    def get_header_insertion_index(self, file_lines: list[str]) -> int:
        """Not used: return NO_LINE_ANCHOR.

        Rely solely on get_header_insertion_char_offset().

        Args:
          file_lines: File content split into lines (unused).

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
        text = original_text
        if not text:
            return 0

        i = 0
        # UTF-8 BOM
        if text.startswith("\ufeff"):
            i += 1

        # Leading ASCII whitespace
        m = re.match(r"[\t \r\n]*", text[i:])
        if m:
            i += m.end()

        # XML declaration
        if text[i : i + 5] == "<?xml":
            end_decl = text.find("?>", i)
            if end_decl == -1:
                return i  # malformed; be conservative
            i = end_decl + 2
            # Whitespace after declaration
            m = re.match(r"[\t \r\n]*", text[i:])
            if m:
                i += m.end()
            # Optional DOCTYPE (best-effort: up to next '>')
            if text[i : i + 9].upper() == "<!DOCTYPE":
                end_doc = text.find(">", i)
                if end_doc != -1:
                    i = end_doc + 1
                m = re.match(r"[\t \r\n]*", text[i:])
                if m:
                    i += m.end()

        # Return current offset; padding handled in prepare_header_for_insertion_text
        return i

    def prepare_header_for_insertion_text(
        self,
        original_text: str,
        insert_offset: int,
        rendered_header_text: str,
    ) -> str:
        """Adjust whitespace so the header block sits on its own lines.

        Approach:
            - If inserting at char>0: ensure exactly one blank line before the block.
            - Always ensure at least one blank line after the block.
            - Preserve the document's dominant newline style (``LF``, ``CR``, ``CRLF``).

        Args:
          original_text (str): Full file content as a single string.
          insert_offset (int): 0-based character offset where the header will be inserted.
          rendered_header_text (str): Header block text (may already include newlines).

        Returns:
          str: Possibly modified header text to splice at ``insert_offset``.
        """
        # Detect newline style
        nl = "\n"
        if original_text.count("\r\n") >= original_text.count("\n") and "\r\n" in original_text:
            nl = "\r\n"

        before = original_text[:insert_offset]
        after = original_text[insert_offset:]

        block = rendered_header_text
        if not (block.endswith("\n") or block.endswith("\r\n")):
            block = block + nl

        # Exactly one blank line before (if not at start)
        if insert_offset > 0:
            # Count trailing newlines in 'before'
            trailing = 0
            j = len(before)
            while j > 0:
                if nl == "\r\n" and before[max(0, j - 2) : j] == "\r\n":
                    trailing += 1
                    j -= 2
                elif before[j - 1 : j] == "\n":
                    trailing += 1
                    j -= 1
                else:
                    break
            if trailing == 0:
                block = nl + nl + block
            elif trailing == 1:
                block = nl + block
            else:
                # already >= one blank line; keep as-is
                pass

        # Ensure at least one blank line after
        if not (after.startswith("\n") or after.startswith("\r\n")):
            block = block + nl

        return block

    def prepare_header_for_insertion(
        self,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
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

        Returns:
          list[str]: Possibly modified header lines including any added padding.
        """
        nl = detect_newline(original_lines)
        out = list(rendered_header_lines)

        # Leading padding
        if insert_index > 0:
            prev_is_blank = (
                insert_index - 1 < len(original_lines)
                and original_lines[insert_index - 1].strip() == ""
            )
            if not prev_is_blank:
                out = [nl] + out

        # Trailing padding
        next_is_blank = insert_index < len(original_lines) and (
            original_lines[insert_index].strip() == ""
        )
        if not next_is_blank:
            out = out + [nl]

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
          lines: Full file content split into lines.
          idx: Zero-based line index to test.

        Returns:
          bool: ``True`` if inside a code fence; ``False`` otherwise.
        """
        import re as _re

        fence = _re.compile(r"^\s*(```|~~~)")
        open_count = 0
        for i in range(0, min(idx + 1, len(lines))):
            if fence.match(lines[i]):
                open_count += 1
        return (open_count % 2) == 1

    def strip_header_block(
        self, *, lines: list[str], span: tuple[int, int] | None = None
    ) -> tuple[list[str], tuple[int, int] | None]:
        """Remove the TopMark header block and return the updated file image.

        This XML/HTML-specific override performs extra cleanup:
          1) Delegates to base removal.
          2) Removes all surrounding blank lines (not just one).
          3) Removes a tightly-wrapping <!-- ... --> block if present.
          4) Collapses the XML declaration and the next element back onto one line.
        """
        # 1) Perform the generic removal first.
        new_lines, removed = super().strip_header_block(lines=lines, span=span)
        if removed is None:
            return new_lines, None

        start, _ = removed

        # --- Blank line cleanup around the removed header ---
        # After base removal, `start` points at the first line that originally
        # followed the header. Our insertion logic may have introduced *one or more*
        # blank lines both before and after the header. We normalize these by
        # deleting all contiguous blank lines after `start`, and then all contiguous
        # blank lines immediately before `start`.

        # 2a) Remove all trailing blanks at `start`, not just one.
        while 0 <= start < len(new_lines) and new_lines[start].strip() == "":
            del new_lines[start]
            # `start` still points to the first content line after the header.

        # 2b) Remove all preceding blanks right before `start`.
        while 0 < start <= len(new_lines) and new_lines[start - 1].strip() == "":
            del new_lines[start - 1]
            start -= 1  # shift left because we deleted just before `start`

        # --- Remove a tightly wrapping block comment (`<!--` ... `-->`) if present ---
        # After deletion of the inner START..END marker lines, we can be left with the
        # outer wrapper lines. If the nearest non-blank line before `start` is exactly
        # the block prefix and the nearest non-blank line at/after `start` is exactly
        # the block suffix, drop both.
        prev_idx = start - 1
        # walk back to previous non-blank
        while 0 <= prev_idx < len(new_lines) and new_lines[prev_idx].strip() == "":
            prev_idx -= 1
        next_idx = start
        # walk forward to next non-blank
        while 0 <= next_idx < len(new_lines) and new_lines[next_idx].strip() == "":
            next_idx += 1

        if (
            0 <= prev_idx < len(new_lines)
            and 0 <= next_idx < len(new_lines)
            and new_lines[prev_idx].strip() == (self.block_prefix or "")
            and new_lines[next_idx].strip() == (self.block_suffix or "")
            and prev_idx < next_idx
        ):
            # Delete suffix first, then prefix to preserve indices
            del new_lines[next_idx]
            del new_lines[prev_idx]
            # After removing the prefix at prev_idx, `start` shifts left if it was
            # beyond prev_idx. Recompute `start` as the first non-blank that follows
            # the (now removed) wrapper region.
            start = prev_idx
            while 0 <= start < len(new_lines) and new_lines[start].strip() == "":
                del new_lines[start]
            # remove any residual blanks immediately before
            while 0 < start <= len(new_lines) and new_lines[start - 1].strip() == "":
                del new_lines[start - 1]
                start -= 1

        # --- Collapse declaration + following element back onto one line ---
        prev_idx = start - 1
        next_idx = start
        if 0 <= prev_idx < len(new_lines) and 0 <= next_idx < len(new_lines):
            prev = new_lines[prev_idx]
            next_line = new_lines[next_idx]

            # Allow for a UTF‑8 BOM and incidental leading whitespace on the decl line.
            prev_no_bom = prev.lstrip("\ufeff")

            # Recognize an XML declaration regardless of whether it currently ends with
            # a newline. Collapse boundary whitespace so there is *no* newline between
            # the declaration and the next node, restoring single‑line layout.
            if prev_no_bom.lstrip().startswith("<?xml"):
                merged = prev.rstrip("\r\n") + next_line.lstrip()
                new_lines[prev_idx : next_idx + 1] = [merged]

        return new_lines, removed
