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

from topmark.filetypes.base import InsertCapability, InsertCheckResult, PreInsertContextView

if TYPE_CHECKING:
    from topmark.pipeline.processors.base import HeaderProcessor

# --- Local helpers for strict XML gate ---
_BOM = "\ufeff"


def _strip_bom(s: str) -> str:
    return s.lstrip(_BOM)


_DEF_WS = " \t\r\n"


def _is_effectively_empty(text: str) -> bool:
    # Consider BOM + ASCII whitespace as empty
    return _strip_bom(text).strip(_DEF_WS) == ""


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
    # Only act for XML-family types; other types OK
    ftname: str = (ctx.file_type.name if ctx.file_type else "").lower()
    xml_like: set[str] = {"xml", "xhtml", "xsl", "xslt", "svg"}
    if ftname not in xml_like:
        return {
            "capability": InsertCapability.OK,
            "origin": origin,
        }

    text: str = "".join(ctx.file_lines or [])
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

    # Unsafe reflow: insertion would split a physical line (no EOL before body).
    # If there is no newline before the insertion offset and body content follows,
    # adding a header would reformat the document (convert one line into multiple).
    if 0 < offset < len(text):
        prev: str = text[offset - 1]
        if prev not in ("\n", "\r"):
            return {
                "capability": InsertCapability.SKIP_UNSUPPORTED_CONTENT,
                "reason": (
                    "XML prolog and body share a line; inserting a header would reflow content"
                ),
                "origin": origin,
            }

    return {
        "capability": InsertCapability.OK,
        "origin": origin,
    }
