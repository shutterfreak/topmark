# topmark:header:start
#
#   project      : TopMark
#   file         : json_like.py
#   file_relpath : src/topmark/filetypes/checks/json_like.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pre-insert checker for JSON-like files.

This module provides a check to determine if inserting a header into a JSON-like
file (including JSONC) is advisable. It ensures that plain JSON files without
comments are not promoted to JSONC unless explicitly allowed.
"""

from __future__ import annotations

from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.filetypes.base import InsertCapability, InsertCheckResult, PreInsertContextView


def json_like_can_insert(
    ctx: PreInsertContextView, *, allow_promote: bool = False
) -> InsertCheckResult:
    """Check if it's advisable to insert a header into a JSON-like file.

    JSONC (JSON with comments) files can always accept headers. Plain JSON files
    do not support comments, so inserting a header would violate the format.
    This check advises against insertion into plain JSON files unless they
    already contain non-Topmark comments (indicating they are actually JSONC),
    or if `allow_promote` is set to True (indicating that the user is okay
    with promoting the file to JSONC).

    Args:
        ctx (PreInsertContextView): A minimal view of the processing context,
            including `file_type`, `file_lines`, and `header_processor`.
        allow_promote (bool): If True, allows promoting plain JSON to JSONC
            by inserting a header even if no comments are present. Defaults to False.

    Returns:
        InsertCheckResult: A dictionary with:
            * `capability` (InsertCapability): Advisory on whether insertion is OK
                or should be skipped (and why).
            * `reason` (str, optional): Human-readable explanation for the advisory.
    """
    origin: str = f"{__name__}.json_like_can_insert"

    # Only act for JSON-family types; other types OK
    ftname: str = (ctx.file_type.name if ctx.file_type else "").lower()
    if ftname not in ("jsonc", "json-with-comments"):
        return {
            "capability": InsertCapability.OK,
            "origin": origin,
        }

    text: str = "".join(ctx.lines or [])
    has_non_topmark_comment: bool = ("//" in text or "/*" in text) and (
        TOPMARK_START_MARKER not in text and TOPMARK_END_MARKER not in text
    )

    if has_non_topmark_comment or allow_promote:
        return {
            "capability": InsertCapability.OK,
            "origin": origin,
        }

    return {
        "capability": InsertCapability.SKIP_POLICY,
        "reason": "JSON lacks comments; promotion to JSONC is disabled",
        "origin": origin,
    }
