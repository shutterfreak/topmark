# topmark:header:start
#
#   project      : TopMark
#   file         : xml.py
#   file_relpath : src/topmark/processors/builtins/xml.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Processor for files with HTML/XML-style block comments (<!-- ... -->).

This processor supports files using `<!-- ... -->`-style comments, such as Markdown.
It delegates header processing to the core pipeline dispatcher.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import ClassVar

from topmark.core.logging import get_logger
from topmark.pipeline.policy_whitespace import is_pure_spacer
from topmark.processors.base import HeaderProcessor
from topmark.processors.types import StripDiagnostic
from topmark.processors.types import StripHeaderResult

if TYPE_CHECKING:
    from topmark.core.logging import TopmarkLogger
    from topmark.filetypes.policy import FileTypeHeaderPolicy

logger: TopmarkLogger = get_logger(__name__)


def _find_doctype_end(text: str, start: int) -> int | None:
    """Return the exclusive end of a simple DOCTYPE declaration.

    The scan ignores ``>`` inside quoted identifiers and inside an internal
    subset. It intentionally remains a small positioning helper rather than an
    XML parser.
    """
    subset_depth = 0
    quote: str | None = None
    for index in range(start + len("<!DOCTYPE"), len(text)):
        char: str = text[index]
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "[":
            subset_depth += 1
        elif char == "]" and subset_depth:
            subset_depth -= 1
        elif char == ">" and subset_depth == 0:
            return index + 1
    return None


def _consume_ascii_whitespace(text: str, offset: int) -> int:
    """Return the offset after XML's supported leading ASCII whitespace."""
    suffix: str = text[offset:]
    return offset + len(suffix) - len(suffix.lstrip("\t \r\n"))


def _ends_with_xml_prolog(text: str) -> bool:
    """Return whether ``text`` ends immediately after a declaration or DOCTYPE."""
    trimmed: str = text.rstrip("\t \r\n")
    without_leading: str = trimmed.lstrip("\ufeff\t \r\n")
    if without_leading.startswith("<?xml") and trimmed.endswith("?>"):
        return True

    doctype_start: int = trimmed.upper().rfind("<!DOCTYPE")
    return doctype_start >= 0 and _find_doctype_end(trimmed, doctype_start) == len(trimmed)


def _standard_line_index(text: str, offset: int) -> int:
    """Translate a character offset for CR, LF, and CRLF input to a line index."""
    prefix: str = text[:offset]
    return prefix.count("\n") + prefix.count("\r") - prefix.count("\r\n")


class XmlHeaderProcessor(HeaderProcessor):
    """Header processor for XML/HTML-like formats.

    This processor uses the **character-offset** strategy for placement:
    `get_header_insertion_index()` returns `NO_LINE_ANCHOR` and
    `get_header_insertion_char_offset()` computes the insertion offset. The
    pipeline falls back to line-based insertion only when no offset is returned.

    It still leverages the base processor for rendering, whitespace alignment,
    and policy-aware behavior where applicable.
    """

    local_key: ClassVar[str] = "xml"
    description: ClassVar[str] = (
        "Header processor for files with HTML/XML-style block comments (<!-- ... -->)."
    )

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
            file_lines: File content split into lines (unused).

        Returns:
            ``NO_LINE_ANCHOR`` to signal char-offset insertion.
        """
        from topmark.processors.base import NO_LINE_ANCHOR

        return NO_LINE_ANCHOR

    def get_header_insertion_char_offset(self, original_text: str) -> int | None:
        """Return a char offset to insert the header for XML/HTML-like documents.

        Handles optional BOM, XML declaration, optional DOCTYPE (including simple
        internal subsets), and consumes whitespace after the prolog if present. Works
        even when the root element follows on the same line.

        Args:
            original_text: Full file content as a single string.

        Returns:
            Character offset suitable for insertion, or ``None`` to use the line-based strategy.
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

        offset = _consume_ascii_whitespace(text, offset)

        # XML declaration
        if text[offset : offset + 5] == "<?xml":
            end_decl: int = text.find("?>", offset)
            if end_decl == -1:
                logger.warning(
                    "xml.insert.char: malformed decl; i=%d; head=%r", offset, original_text[:40]
                )
                return offset  # malformed; be conservative
            offset = end_decl + 2
            offset = _consume_ascii_whitespace(text, offset)
            # Optional DOCTYPE (best-effort, including a simple internal subset)
            if text[offset : offset + 9].upper() == "<!DOCTYPE":
                doctype_start: int = offset
                end_doc: int | None = _find_doctype_end(text, offset)
                if end_doc is None:
                    return doctype_start
                offset = end_doc
                offset = _consume_ascii_whitespace(text, offset)

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
            original_text: Full file content as a single string.
            insert_offset: 0-based character offset where the header will be inserted.
            rendered_header_text: Header block text (may already include newlines).
            newline_style: Newline style (``LF``, ``CR``, ``CRLF``).

        Returns:
            Possibly modified header text to splice at ``insert_offset``.
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
        if not (block.endswith("\n") or block.endswith("\r")):
            block = block + newline_style

        # --- Leading padding (after prolog/doctype, always for XML-like) ---
        # Add a single blank line *only* when inserting after a prolog/doctype and
        # the previous logical line is not already a policy-blank.
        add_leading_blank: bool = False
        prev_char_is_eol: bool = False
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

            # Internal subsets have no useful fixed maximum length, so inspect the
            # complete prefix rather than relying on a bounded line look-back.
            after_prolog: bool = _ends_with_xml_prolog(original_text[:insert_offset])
            prev_char_is_eol: bool = original_text[insert_offset - 1] in ("\n", "\r")

            if after_prolog and not is_pure_spacer(prev_line, policy):
                add_leading_blank = True

        if add_leading_blank:
            # If we are splitting a single physical line (prolog + root on one line),
            # we need two newlines: one to end the prolog line and one blank line.
            # If the prolog already ended with an EOL, we only need one blank line.
            block = newline_style * 2 + block if not prev_char_is_eol else newline_style + block

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
            original_lines: Original file lines.
            insert_index: Line index where the header will be inserted.
            rendered_header_lines: Header lines to insert.
            newline_style: Newline style (``LF``, ``CR``, ``CRLF``).

        Returns:
            Possibly modified header lines including any added padding.
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

            # A DOCTYPE internal subset can span any number of physical lines.
            after_prolog: bool = _ends_with_xml_prolog("".join(original_lines[:insert_index]))

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

        Applies the base proximity rules to ensure the detected header appears
        close to the expected insertion anchor (after prolog/doctype) and not
        in an obviously invalid location. Markdown-specific safeguards for
        fenced code blocks are handled by `MarkdownHeaderProcessor`.

        Args:
            lines: Full file content split into lines.
            header_start_idx: 0-based index of the candidate header's first line.
            header_end_idx: 0-based index of the candidate header's last line (inclusive).
            anchor_idx: 0-based expected insertion line index.

        Returns:
            ``True`` if the candidate is acceptable; ``False`` otherwise.
        """
        text: str = "".join(lines)
        char_offset: int | None = self.get_header_insertion_char_offset(text)
        # A line-only fallback anchor may point inside a multiline DOCTYPE. Use
        # the exact XML insertion boundary when deciding whether a header is current.
        effective_anchor: int = (
            anchor_idx if char_offset is None else _standard_line_index(text, char_offset)
        )

        return super().validate_header_location(
            lines,
            header_start_idx=header_start_idx,
            header_end_idx=header_end_idx,
            anchor_idx=effective_anchor,
        )

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> StripHeaderResult:
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
            lines: Full file content split into lines (keepends=True).
            span: Optional (start, end) indices of the header block to remove; if ``None``,
                the base class attempts auto-detect.
            newline_style: Newline style (``LF``, ``CR``, ``CRLF``).
            ends_with_newline: Whether the original file ended with a newline; not used by this
                simplified implementation but kept for signature compatibility.

        Returns:
            Structured strip result containing the updated file lines, the
            inclusive removed span when a header was removed, and the diagnostic
            describing the outcome.
        """
        # Delegate policy-aware detection and removal to the base implementation
        strip_result: StripHeaderResult = super().strip_header_block(
            lines=lines,
            span=span,
            newline_style=newline_style,
            ends_with_newline=ends_with_newline,
        )

        # XML-specific tweak: if a header was removed and policy ensures a spacer after header,
        # drop exactly one spacer line that matches the file's newline style (no whitespace-only).
        if strip_result.removed_span is None:
            return strip_result

        policy: FileTypeHeaderPolicy | None = (
            self.file_type.header_policy if self.file_type else None
        )

        # Remove *one* trailing spacer that we likely introduced after the header
        # (only when policy asked for it). Never touch pre-header blanks or the prolog.
        if not policy or not bool(getattr(policy, "ensure_blank_after_header", False)):
            return strip_result

        start: int
        _end: int
        start, _end = strip_result.removed_span
        if not (0 <= start < len(strip_result.lines)) or not is_pure_spacer(
            strip_result.lines[start], policy
        ):
            return strip_result

        updated_lines: list[str] = list(strip_result.lines)
        del updated_lines[start]
        updated_notes: list[str] = [
            *strip_result.diagnostic.notes,
            "xml: removed one trailing spacer per policy",
        ]

        return StripHeaderResult(
            lines=updated_lines,
            removed_span=strip_result.removed_span,
            diagnostic=StripDiagnostic(
                kind=strip_result.diagnostic.kind,
                reason=strip_result.diagnostic.reason,
                removed_span=strip_result.diagnostic.removed_span,
                notes=updated_notes,
            ),
        )
