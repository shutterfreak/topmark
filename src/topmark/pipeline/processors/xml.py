# topmark:header:start
#
#   file         : xml.py
#   file_relpath : src/topmark/pipeline/processors/xml.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""
Processor for files with HTML/XML-style block comments (<!-- ... -->).

This processor supports files using `<!-- ... -->`-style comments, such as MarkDown.
It delegates header processing to the core pipeline dispatcher.
"""

import re

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
    """
    Processor for files with HTML/XML-style block comments (<!-- ... -->).

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
        """
        from .base import NO_LINE_ANCHOR

        return NO_LINE_ANCHOR

    def get_header_insertion_char_offset(self, original_text: str) -> int | None:
        """Return a char offset to insert the header for XML/HTML-like documents.

        Handles optional BOM, XML declaration, optional DOCTYPE (including simple
        internal subsets), and consumes whitespace after the prolog if present.
        Works even when the root element follows on the same line.
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
        r"""Adjust whitespace so the header block sits on its own lines.

        Approach:
            - If inserting at char>0: ensure exactly one blank line before the block.
            - Always ensure at least one blank line after the block.
            - Preserve the document's dominant newline style ("\n" or "\r\n").
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
        """

        def detect_newline(lines: list[str]) -> str:
            for ln in lines:
                if ln.endswith("\r\n"):
                    return "\r\n"
                if ln.endswith("\n"):
                    return "\n"
                if ln.endswith("\r"):
                    return "\r"
            return "\n"

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

        This override enforces the base proximity rule relative to the computed
        anchor and adds a Markdown-specific safeguard. If the current file type
        is Markdown, candidate headers that appear *inside* fenced code blocks
        (lines starting with ```
        or ``~~~``) are rejected so that example
        snippets in README files are not treated as real headers.

        Args:
            lines: Full file content split into lines.
            header_start_idx: 0-based index of the candidate header's first line.
            header_end_idx: 0-based index of the candidate header's last line (inclusive).
            anchor_idx: 0-based index of the line where the header is expected to be inserted.

        Returns:
            True if the candidate is close enough to the anchor and, for Markdown,
            not inside a fenced code block; False otherwise.
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
        import re as _re

        fence = _re.compile(r"^\s*(```|~~~)")
        open_count = 0
        for i in range(0, min(idx + 1, len(lines))):
            if fence.match(lines[i]):
                open_count += 1
        return (open_count % 2) == 1
