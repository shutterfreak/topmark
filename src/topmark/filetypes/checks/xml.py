# topmark:header:start
#
#   project      : TopMark
#   file         : xml.py
#   file_relpath : src/topmark/filetypes/checks/xml.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pre-insert checker for XML files.

Provides a function to determine whether it is safe to insert headers into XML files,
ensuring the presence of a body beyond declarations or doctypes.
"""

from typing import TYPE_CHECKING

from topmark.filetypes.base import (
    InsertCapability,
    InsertCheckResult,
    PreInsertContextView,
)

if TYPE_CHECKING:
    from topmark.pipeline.processors.base import HeaderProcessor

# --- Local helpers for strict XML gate ---
_BOM = "\ufeff"


def _strip_bom(s: str) -> str:
    return s.lstrip(_BOM)


_DEF_WS: str = " \t\r\n"
# Treat Unicode newline equivalents like NEL/LS/PS as line breaks for heuristics.
# U+0085 (NEL), U+2028 (Line Separator), U+2029 (Paragraph Separator)
_NL_EQUIV: set[str] = {"\n", "\r", "\x85", "\u2028", "\u2029"}


def _is_newline_equiv(ch: str) -> bool:  # pyright: ignore[reportUnusedFunction]
    return ch in _NL_EQUIV


def _is_effectively_empty(text: str) -> bool:
    # Consider BOM + ASCII whitespace as empty
    return _strip_bom(text).strip(_DEF_WS) == ""


def _offset_to_line_col(lines: list[str], offset: int) -> tuple[int, int]:
    """Map a character offset in the *concatenated* text to (line_index, col).

    `lines` must be keepends=True. Works for LF/CRLF/CR because we count
    the raw length of each element (including its terminator).
    """
    if not lines:
        return (0, 0)
    acc = 0
    for i, ln in enumerate(lines):
        nxt = acc + len(ln)
        if offset < nxt:
            return (i, offset - acc)
        acc = nxt
    # Past-the-end safeguard: clamp to last line
    return (len(lines) - 1, max(0, offset - acc))


def xml_can_insert(ctx: PreInsertContextView) -> InsertCheckResult:
    """Check if it's safe to insert a header into an XML file.

    The check ensures that the XML file has a body (not just a declaration or
    doctype) before allowing header insertion. If the file consists solely of an
    XML declaration and/or doctype, insertion is deemed unsupported.

    Args:
        ctx (PreInsertContextView): A minimal view of the processing context,
            including `file_type`, `file_lines`, and `header_processor`.

    Returns:
        InsertCheckResult: A dictionary with:
            * `capability` (InsertCapability): Advisory on whether insertion is OK
                or should be skipped (and why).
            * `reason` (str, optional): Human-readable explanation for the advisory.
    """
    origin: str = f"{__name__}.xml_can_insert"
    lines: list[str] = list(ctx.lines or [])
    text: str = "".join(lines)
    proc: HeaderProcessor | None = ctx.header_processor
    if not proc or not hasattr(proc, "get_header_insertion_char_offset"):
        return {
            "capability": InsertCapability.SKIP_OTHER,
            "reason": "no XML processor",
            "origin": origin,
        }

    # Empty or whitespace-only (after BOM) → unsafe
    if _is_effectively_empty(text):
        return {
            "capability": InsertCapability.SKIP_UNSUPPORTED_CONTENT,
            "reason": "Empty or whitespace-only XML (no body)",
            "origin": origin,
        }

    # Unterminated XML declaration (present but no closing '?>') → unsafe
    if text.lstrip(_BOM).startswith("<?xml") and "?>" not in text:
        return {
            "capability": InsertCapability.SKIP_UNSUPPORTED_CONTENT,
            "reason": "Unterminated XML declaration",
            "origin": origin,
        }

    # Unterminated DOCTYPE (present but no closing '>') → unsafe (best-effort)
    # We don’t fully parse internal subsets; this is a pragmatic guard.
    if "<!DOCTYPE" in text.upper() and ">" not in text[text.upper().find("<!DOCTYPE") :]:
        return {
            "capability": InsertCapability.SKIP_UNSUPPORTED_CONTENT,
            "reason": "Unterminated DOCTYPE declaration",
            "origin": origin,
        }

    try:
        offset: int | None = proc.get_header_insertion_char_offset(text)
    except Exception:
        return {
            "capability": InsertCapability.SKIP_OTHER,
            "reason": "xml offset error",
            "origin": origin,
        }

    if offset is None:
        return {
            "capability": InsertCapability.SKIP_OTHER,
            "reason": "no insertion offset",
            "origin": origin,
        }

    if offset == len(text):  # EOF after decl/doctype → prolog-only
        return {
            "capability": InsertCapability.SKIP_UNSUPPORTED_CONTENT,
            "reason": "XML declaration/doctype only (no body)",
            "origin": origin,
        }

    # Idempotence risks and content legality checks:
    # (A) Reflow: prolog and body share a physical line (no newline-equivalent before body)
    #     Inserting a multi-line header would split that physical line.
    # (B) Ambiguous padding: body begins with a *non-standard* newline-equivalent (NEL/LS/PS).
    #     Our current inserter adds a standard '\n\n' separator; stripper may not collapse it
    #     back when mixed with NEL/LS/PS, leading to non-idempotent insert→strip→insert.
    # (C) Illegal controls on the **first body line** (XML 1.0): any C0 control below 0x20
    #     except TAB (#x9), LF (#xA), CR (#xD). Example: U+001E (Record Separator).
    if 0 <= offset < len(text):
        # Locate the insertion point within file_lines (keepends=True).
        line_idx: int
        col: int
        line_idx, col = _offset_to_line_col(lines, offset)

        # (A) Reflow: insertion splits a physical line (col > 0).
        # Inserting a multi-line header mid-line is non-idempotent by design.
        if col > 0:
            return {
                "capability": InsertCapability.SKIP_IDEMPOTENCE_RISK,
                "reason": "XML prolog and body share a line; header insertion would reflow content",
                "origin": origin,
            }
        # Compute the first two *logical* body lines starting at offset,
        # independent of whether the file uses LF/CRLF/CR. We examine the slice
        # from `col` to EOL on the first line, then the next full line.
        body_slices: list[str] = []
        if 0 <= line_idx < len(lines):
            # first line portion (strip only CR/LF terminators)
            first_core: str = lines[line_idx][col:].rstrip("\r\n")
            body_slices.append(first_core)
        if line_idx + 1 < len(lines):
            second_core: str = lines[line_idx + 1].rstrip("\r\n")
            body_slices.append(second_core)

        # (B) Ambiguous padding: if any of the first two body **lines** contains a
        # Unicode newline variant (NEL/LS/PS), our separator handling may not be
        # idempotent (mixing with our exact blank yields drift). This covers cases
        # where a NEL appears at the start of the *second* line.
        if body_slices:
            for slice_text in body_slices[:2]:
                if slice_text and any(ch in {"\x85", "\u2028", "\u2029"} for ch in slice_text):
                    return {
                        "capability": InsertCapability.SKIP_IDEMPOTENCE_RISK,
                        "reason": (
                            "Early XML body contains non-standard newline (NEL/LS/PS); "
                            "idempotence not guaranteed"
                        ),
                        "origin": origin,
                    }

        # (C) XML 1.0 legality: Disallowed C0 controls on the *initial body region*
        # (first two logical lines). Anything < 0x20 except TAB/LF/CR should cause
        # a refusal rather than trying to normalize user data.
        for slice_text in body_slices:
            for ch in slice_text:
                code: int = ord(ch)
                if 0x00 <= code < 0x20 and ch not in {"\t", "\n", "\r"}:
                    return {
                        "capability": InsertCapability.SKIP_UNSUPPORTED_CONTENT,
                        "reason": f"Disallowed control U+{code:04X} in early XML body lines",
                        "origin": origin,
                    }

    return {
        "capability": InsertCapability.OK,
        "origin": origin,
    }
