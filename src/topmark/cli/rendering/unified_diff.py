# topmark:header:start
#
#   project      : TopMark
#   file         : unified_diff.py
#   file_relpath : src/topmark/cli/rendering/unified_diff.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""Unified diff rendering helpers for CLI (optional ANSI styling).

This module formats unified diffs for human-facing CLI output. It is allowed to
depend on a styling backend (currently `yachalk`) and provides a single helper
that can emit either styled or plain output depending on the caller's color
settings.

Notes:
    - Control characters such as CR/LF are escaped ("\\r", "\\n") so previews are stable.
    - For non-ANSI contexts (or when color is disabled), callers can either set
      `color=False` or use `topmark.utils.diff.format_patch_text`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.core.presentation import StyleRole

if TYPE_CHECKING:
    from collections.abc import Sequence


def format_patch_styled(
    *,
    patch: Sequence[str] | str,
    color: bool,
    show_line_numbers: bool = False,
) -> str:
    """Render a styled (optionally colorized) preview of a unified diff.

    This formatter is intentionally structure-aware: it styles unified diff *file headers*
    (the `---` / `+++` lines) only when they appear in the expected header slot, and it
    styles add/del/context lines only when inside a hunk. This avoids accidental styling
    of content that happens to start with `---` / `+++` / `+` / `-` (e.g. `--->`).

    Notes:
        TopMark generates diffs via `difflib.unified_diff`, which means:
        - there is no "diff ..." preamble
        - the first two lines are the file headers (`--- ...` then `+++ ...`)
        This implementation follows that contract but remains defensive if the input is truncated or
        malformed.

    Args:
        patch: A unified diff as either a list/sequence of lines or a single multiline string.
        color: Whether to emit ANSI-styled output.
        show_line_numbers: Whether to prefix output with line numbers.

    Returns:
        The formatted diff preview.
    """
    # Normalize input to a list of lines (no trailing newlines)
    if isinstance(patch, str):
        lines: list[str] = patch.splitlines(keepends=False)
    else:
        # Convert to list to allow multiple passes
        lines = list(patch)

    # Resolve stylers once (when `color=False` these resolve to no-ops via style_for_role).
    def styler(role: StyleRole) -> TextStyler:
        return style_for_role(role, styled=color)

    style_meta: TextStyler = styler(StyleRole.DIFF_META)
    style_header: TextStyler = styler(StyleRole.DIFF_HEADER)
    style_add: TextStyler = styler(StyleRole.DIFF_ADD)
    style_del: TextStyler = styler(StyleRole.DIFF_DEL)
    style_context: TextStyler = styler(StyleRole.NO_STYLE)
    style_fallback: TextStyler = styler(StyleRole.WARNING)
    style_fallback: TextStyler = styler(StyleRole.NO_STYLE)
    style_line_no: TextStyler = styler(StyleRole.DIFF_LINE_NO)

    def escape_controls(line: str) -> str:
        # Make previews stable and explicit.
        return line.replace("\r", "\\r").replace("\n", "\\n")

    def is_file_header_old(line: str) -> bool:
        # Require a space or tab after the marker so content like `--->` does not match.
        return line.startswith("--- ") or line.startswith("---\t")

    def is_file_header_new(line: str) -> bool:
        return line.startswith("+++ ") or line.startswith("+++\t")

    def is_hunk_header(line: str) -> bool:
        return line.startswith("@@")

    def is_no_newline_marker(line: str) -> bool:
        return line.startswith("\\")

    in_hunk: bool = False
    rendered_lines: list[str] = []

    for idx, raw in enumerate(lines):
        # idx is 0-based; i is 1-based for line numbers
        i: int = idx + 1
        line: str = raw
        content: str = escape_controls(line)

        # Header slot styling (difflib contract):
        # line 1 => `--- ...`, line 2 => `+++ ...`
        if idx == 0 and is_file_header_old(line):
            in_hunk = False
            rendered: str = style_header(content)
        elif idx == 1 and is_file_header_new(line):
            in_hunk = False
            rendered = style_header(content)

        # Hunks / metadata
        elif is_hunk_header(line):
            in_hunk = True
            rendered = style_meta(content)
        elif is_no_newline_marker(line):
            rendered = style_meta(content)

        # Hunk body classification (only inside hunks)
        elif in_hunk and line.startswith("+"):
            rendered = style_add(content)
        elif in_hunk and line.startswith("-"):
            rendered = style_del(content)
        elif in_hunk and line.startswith(" "):
            rendered = style_context(content)

        # Outside hunks: do not treat leading +/- as diff markers.
        else:
            rendered = style_fallback(content)

        # Optional line numbers: style only the gutter.
        if show_line_numbers:
            gutter: str = f"{i:04d}|"
            if color:
                rendered_lines.append(style_line_no(gutter) + rendered)
            else:
                rendered_lines.append(gutter + content)
        else:
            rendered_lines.append(rendered)

    # Join with explicit newlines.
    return "".join(f"{ln}\n" for ln in rendered_lines)
