# topmark:header:start
#
#   project      : TopMark
#   file         : template_surgery.py
#   file_relpath : src/topmark/config/io/template_surgery.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Presentation-oriented edits for the bundled config template.

This module performs *text-level* edits on the annotated default configuration
template (``topmark-default.toml``) for copy/paste-friendly CLI output.

Supported transformations:

- ``--pyproject``: ensure an explicit ``[tool.topmark]`` header exists so the
  output can be pasted into ``pyproject.toml``.
- ``--root``: insert/remove a ``root = true`` setting while preserving the
  template's comment layout.

Design goals:

- Preserve the template's original comments and formatting.
- Make edits idempotent (safe to apply repeatedly).
- Be conservative when removing content.
- Provide a TOML-parse backstop and clear error hints.

Rationale:

The annotated template is primarily documentation. Full AST rewriting tends to
reorder content and strip formatting, which is undesirable for human-facing
output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

import tomlkit
from tomlkit.exceptions import ParseError as TomlkitParseError
from tomlkit.items import Item, Table

from topmark.config.logging import TopmarkLogger, get_logger
from topmark.constants import TOPMARK_END_MARKER

_TOOL_TOPMARK_HEADER: Final[str] = "[tool.topmark]"
_ROOT_LINE: Final[str] = "root = true"

logger: TopmarkLogger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TemplateEditResult:
    """Result of applying a text edit to the template.

    Attributes:
        text: Edited TOML text.
        changed: True if the returned text differs from the input.
    """

    text: str
    changed: bool


def ensure_pyproject_header(toml_text: str) -> TemplateEditResult:
    """Ensure the template contains an explicit ``[tool.topmark]`` table header."""
    lines: list[str] = toml_text.splitlines(keepends=True)

    # IMPORTANT: avoid false positives from inline documentation mentioning "[tool.topmark]".
    # We must only treat *actual table headers* as present. Detection therefore checks for a line
    # that starts with `[tool.topmark]` (and is not a comment), rather than searching the raw text.
    for line in lines:
        if line.startswith(_TOOL_TOPMARK_HEADER):
            logger.debug("ensure_pyproject_header(): '%s' already present.", _TOOL_TOPMARK_HEADER)
            return TemplateEditResult(text=toml_text, changed=False)

    # Find end of topmark header block, if present
    insert_at = 0
    # Placement rule:
    # - If a TopMark header block exists (``# topmark:header:start`` … ``# topmark:header:end``),
    #   insert right after the end marker and any following blank lines.
    # - Otherwise, insert at the start of the file.
    for i, line in enumerate(lines):
        if line.strip() == f"# {TOPMARK_END_MARKER}":
            insert_at: int = i + 1
            # Skip following blank lines
            while insert_at < len(lines) and lines[insert_at].strip() == "":
                insert_at += 1
            break

    logger.debug(
        "Will insert '%s' at line %d",
        _TOOL_TOPMARK_HEADER,
        insert_at,
    )

    header_line = _TOOL_TOPMARK_HEADER + "\n"
    spacer = "\n"  # keep a visual gap between the header and the banner/comments

    lines.insert(insert_at, header_line)
    lines.insert(insert_at + 1, spacer)

    # Idempotent: if a real ``[tool.topmark]`` header is already present, no changes are made.
    return TemplateEditResult(text="".join(lines), changed=True)


def set_root_flag_in_template_text(
    toml_text: str,
    *,
    root: bool,
) -> TemplateEditResult:
    """Insert or remove ``root = true`` in the template text while preserving layout.

    This function edits the annotated template as text (not as a TOML AST) so the
    surrounding documentation and spacing remain intact.

    Placement when enabling ``root``:

    1) Preferred: insert immediately after the *example anchor* comment line
       ``# root = true`` (in the discovery/docs section). This keeps the real setting
       adjacent to the inline documentation.

    2) Fallback: insert near the beginning (after an optional TopMark header block).

    Scope semantics:

    - If a real ``[tool.topmark]`` header exists, the inserted ``root = true`` is
      placed directly under it so it becomes ``tool.topmark.root``.
    - Otherwise, ``root = true`` is inserted at the document top-level.

    Idempotency:

    - Enabling: if an exact standalone ``root = true`` already exists in the
      appropriate scope, no changes are made.
    - Disabling: only exact standalone non-comment ``root = true`` lines are removed.

    Args:
        toml_text: TOML document text.
        root: Whether to enable the root flag. If False, any exact standalone
            non-comment ``root = true`` lines are removed.

    Returns:
        TemplateEditResult with edited text and a ``changed`` flag.
    """
    lines: list[str] = toml_text.splitlines(keepends=True)

    def _is_comment(line: str) -> bool:
        return line.lstrip().startswith("#")

    def _is_real_header(line: str, header: str) -> bool:
        # Must be an actual table header line, not a mention in a comment.
        return (not _is_comment(line)) and line.startswith(header)

    def _is_root_line(line: str) -> bool:
        # Exact standalone `root = true`, not commented.
        return (not _is_comment(line)) and (line.strip() == _ROOT_LINE)

    # Locate the first real `[tool.topmark]` header (if present)
    tool_topmark_idx: int | None = None
    for i, line in enumerate(lines):
        if _is_real_header(line, _TOOL_TOPMARK_HEADER):
            tool_topmark_idx = i
            break

    # Collect all existing standalone `root = true` lines (non-comment)
    root_idxs: list[int] = [i for i, line in enumerate(lines) if _is_root_line(line)]
    has_root_true: bool = bool(root_idxs)

    # Fast path idempotency for "remove"
    if not root and not has_root_true:
        return TemplateEditResult(text=toml_text, changed=False)

    if not root:
        # Conservative removal: remove exact standalone `root = true` lines only.
        new_lines: list[str] = []
        changed = False
        for line in lines:
            if _is_root_line(line):
                changed = True
                continue
            new_lines.append(line)
        return TemplateEditResult(text="".join(new_lines), changed=changed)

    # root=True insertion path
    #
    # IMPORTANT semantic constraint:
    # - If `[tool.topmark]` exists, `root = true` must appear *after* it and *before*
    #   any `[tool.topmark.*]` subtables, otherwise it won't be `tool.topmark.root`.
    #
    # Therefore, in "pyproject-style" templates we prefer inserting right after
    # `[tool.topmark]` rather than near the docs anchor comment.
    insert_at: int | None = None

    if tool_topmark_idx is not None:
        # Insert just after `[tool.topmark]` and any immediate blank lines.
        insert_at = tool_topmark_idx + 1
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1

        # If the next significant line is already `root = true`, we're done.
        if insert_at < len(lines) and _is_root_line(lines[insert_at]):
            # If there are stray duplicates elsewhere, clean them up for consistency.
            # (We only do this when it would actually change the output.)
            if len(root_idxs) > 1:
                new_lines: list[str] = []
                removed = 0
                for idx, line in enumerate(lines):
                    if _is_root_line(line) and idx != insert_at:
                        removed += 1
                        continue
                    new_lines.append(line)
                return TemplateEditResult(text="".join(new_lines), changed=(removed > 0))
            return TemplateEditResult(text=toml_text, changed=False)

        # If `root = true` exists somewhere else, remove it so we don't end up with
        # top-level root or root under the wrong table.
        if has_root_true:
            new_lines: list[str] = []
            for line in lines:
                if _is_root_line(line):
                    continue
                new_lines.append(line)
            lines = new_lines
            # After removal, recompute insertion index relative to the updated list:
            # tool_topmark_idx is still correct because we only removed `root = true` lines.
            tool_topmark_idx = None
            for i, line in enumerate(lines):
                if _is_real_header(line, _TOOL_TOPMARK_HEADER):
                    tool_topmark_idx = i
                    break
            insert_at = (tool_topmark_idx + 1) if tool_topmark_idx is not None else 0
            while insert_at < len(lines) and lines[insert_at].strip() == "":
                insert_at += 1

        payload = _ROOT_LINE + "\n"
        lines.insert(insert_at, payload)
        # Keep a blank line between `root` and the next section/table header.
        if insert_at + 1 < len(lines) and lines[insert_at + 1].strip() != "":
            lines.insert(insert_at + 1, "\n")
        return TemplateEditResult(text="".join(lines), changed=True)

    # No `[tool.topmark]` header: place near docs anchor if possible (top-level root).
    if has_root_true:
        return TemplateEditResult(text=toml_text, changed=False)

    # 1) Preferred anchor: right after the example comment line "# root = true"
    for i, line in enumerate(lines):
        if line.strip() == "# root = true":
            insert_at = i + 1
            # If next non-empty is already root=true, bail (idempotent)
            j = insert_at
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and _is_root_line(lines[j]):
                return TemplateEditResult(text=toml_text, changed=False)
            break

    # 2) Fallback: after topmark header block (or at file start)
    if insert_at is None:
        insert_at = 0
        for i, line in enumerate(lines):
            if line.strip() == f"# {TOPMARK_END_MARKER}":
                insert_at = i + 1
                while insert_at < len(lines) and lines[insert_at].strip() == "":
                    # Skip blank lines
                    insert_at += 1
                break

    lines.insert(insert_at, _ROOT_LINE + "\n")
    # Ensure a blank line after, unless we already have one
    if insert_at + 1 < len(lines) and lines[insert_at + 1].strip() != "":
        lines.insert(insert_at + 1, "\n")

    return TemplateEditResult(text="".join(lines), changed=True)


def validate_toml_for_config_init(
    toml_text: str,
    *,
    for_pyproject: bool,
    root_expected: bool,
) -> None:
    """Validate a config-init TOML document.

    This is a defensive backstop for presentation-oriented template edits.

    Validates:
        - TOML syntax parses.
        - Minimal expected structure for the selected output mode (plain vs pyproject).
        - Optional ``root`` expectation (top-level vs ``tool.topmark.root``).

    Args:
        toml_text: TOML document text to validate.
        for_pyproject: If True, the document is expected to contain a ``[tool]`` table
            with a nested ``[tool.topmark]`` table.
        root_expected: If True, the document is expected to contain ``root = true`` in
            the appropriate scope (top-level for non-pyproject output, or
            ``tool.topmark.root`` for pyproject output).

    Raises:
        RuntimeError: With an actionable hint when the document does not match the
            selected output mode, or when the document is invalid TOML.
    """
    try:
        doc: tomlkit.TOMLDocument = tomlkit.parse(toml_text)
    except TomlkitParseError as exc:
        raise RuntimeError(f"Invalid TOML produced by template surgery: {exc}") from exc

    def _has_real_header(header: str) -> bool:
        # Only count actual table headers, not comment mentions.
        for line in toml_text.splitlines():
            s = line.lstrip()
            if not s or s.startswith("#"):
                continue
            if s.startswith(header):
                return True
        return False

    if for_pyproject:
        # We expect actual tool/topmark tables in the parsed document.
        if "tool" not in doc:
            raise RuntimeError(
                "Expected pyproject-style output but no [tool] table exists. "
                "This usually means [tool.topmark] was not inserted/nested.\n"
                f"Header scan: has [tool.topmark]={_has_real_header('[tool.topmark]')}, "
                f"has [tool.topmark.header]={_has_real_header('[tool.topmark.header]')}"
            )

        tool_item: Item = cast("Item", doc["tool"])
        if not isinstance(tool_item, Table):
            raise RuntimeError(
                "Expected [tool] to be a TOML table, but it exists and is not a table."
            )

        if "topmark" not in tool_item:
            raise RuntimeError(
                "Expected [tool.topmark] table for pyproject-style output but it is missing.\n"
                "Note: comment mentions of '[tool.topmark]' do not create a table.\n"
                f"Header scan: has [tool.topmark]={_has_real_header('[tool.topmark]')}, "
                f"has [tool.topmark.header]={_has_real_header('[tool.topmark.header]')}"
            )

        topmark_item: Item = tool_item["topmark"]
        if not isinstance(topmark_item, Table):
            raise RuntimeError(
                "Expected [tool.topmark] to be a TOML table, but it exists and is not a table."
            )

        if root_expected:
            if "root" not in topmark_item:
                raise RuntimeError("Expected `tool.topmark.root = true` but `root` key is missing.")
            root_val = topmark_item["root"]
            if getattr(root_val, "value", root_val) is not True:
                raise RuntimeError("Expected `tool.topmark.root = true` but it is not true.")

    else:
        # Non-pyproject mode: root lives at the document top-level.
        if root_expected:
            if "root" not in doc:
                raise RuntimeError("Expected top-level `root = true` but `root` key is missing.")
            root_val = doc["root"]
            if getattr(root_val, "value", root_val) is not True:
                raise RuntimeError("Expected top-level `root = true` but it is not true.")
