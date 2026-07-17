# topmark:header:start
#
#   project      : TopMark
#   file         : mixins.py
#   file_relpath : src/topmark/processors/mixins.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared shebang and line-comment behavior for header processors.

``LineCommentMixin`` supplies the runtime behavior shared by the pound and slash
processors. XML positioning and block-comment padding remain format-specific and
live on their concrete processors rather than behind generic helpers.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Final

from topmark.pipeline.policy_whitespace import is_pure_spacer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.filetypes.policy import FileTypeHeaderPolicy

_RE_SHEBANG: Final[re.Pattern[str]] = re.compile(r"^#!")


class ShebangAwareMixin:
    """Utilities for shebang-aware insertion anchors.

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

    Processors define line-comment delimiter attributes, usually during
    construction:
        * ``line_prefix``: the comment introducer for a header line (e.g., ``# ``).
        * ``line_suffix``: optional trailing comment portion to append (e.g., `` */``).

    Methods here centralize header line normalization, scanning, and safe
    insertion point computation (shebang aware).
    """

    #: Instance-level line comment prefix, e.g., "# ", "// ", "; ", "-- ".
    line_prefix: str = ""
    #: Instance-level suffix appended after content, rare for line comments.
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

        # Read the bound file type policy if present.
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
