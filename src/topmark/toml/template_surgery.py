# topmark:header:start
#
#   project      : TopMark
#   file         : template_surgery.py
#   file_relpath : src/topmark/toml/template_surgery.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Presentation-oriented edits for the bundled example TopMark TOML resource.

This module performs text-level edits on the annotated bundled example TopMark
TOML resource (`topmark-example.toml`) for copy/paste-friendly CLI output.

Supported transformations:
- `--root`: insert or remove `root = true` while preserving the documented
  layout of the example TOML resource
- validation of the final plain or pyproject-shaped output used by
  `topmark config init`

Design goals:
- preserve the resource's original comments and formatting
- make edits idempotent (safe to apply repeatedly)
- be conservative when removing content
- provide a TOML-parse backstop and clear validation hints

Rationale:
The bundled example TopMark TOML resource is primarily documentation. Full AST
rewriting tends to reorder content and strip formatting, which is undesirable
for human-facing output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Final
from typing import cast

import tomlkit
from tomlkit.exceptions import ParseError as TomlkitParseError
from tomlkit.items import Item
from tomlkit.items import Table

from topmark.constants import TOPMARK_END_MARKER
from topmark.core.errors import TemplateValidationError
from topmark.core.logging import TopmarkLogger
from topmark.core.logging import get_logger

if TYPE_CHECKING:
    from tomlkit.container import Container

_TOOL_TOPMARK_HEADER: Final[str] = "[tool.topmark]"
_CONFIG_HEADER: Final[str] = "[config]"
_TOOL_TOPMARK_CONFIG_HEADER: Final[str] = "[tool.topmark.config]"
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
    """Ensure the example TOML text contains an explicit `[tool.topmark]` header."""
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
    for_pyproject: bool,
    root: bool,
) -> TemplateEditResult:
    """Insert or remove `root = true` in example TOML text under `[config]`.

    This function edits the bundled example TOML resource as text (not as a
    TOML AST) so the surrounding documentation and spacing remain intact.

    Placement when enabling `root`:

    1) Preferred: if the appropriate config table already exists, place
       `root = true` inside it, preferring the documented example anchor
       `# root = true` when present.
    2) Otherwise, if a commented-out config table anchor exists in the
       template, uncomment that header and place `root = true` inside it,
       preferring the documented example anchor `# root = true` when present.
    3) Fallback: add a new config table in the appropriate scope and insert
       `root = true` there.

    Scope semantics:

    - For plain `topmark.toml`, the root flag lives under `[config]`.
    - For `pyproject.toml`, the root flag lives under `[tool.topmark.config]`.

    Idempotency:

    - Enabling: if an exact standalone non-comment `root = true` already
      exists inside the correct config table, no changes are made.
    - Disabling: only exact standalone non-comment `root = true` lines inside
      the appropriate config table are removed.

    Args:
        toml_text: Example TOML document text.
        for_pyproject: Whether the target scope is pyproject-style
            (`[tool.topmark.config]`) rather than plain `[config]`.
        root: Whether to enable the root flag.

    Returns:
        TemplateEditResult with edited text and a `changed` flag.
    """
    lines: list[str] = toml_text.splitlines(keepends=True)

    def _is_comment(line: str) -> bool:
        return line.lstrip().startswith("#")

    def _is_real_header(line: str, header: str) -> bool:
        # Must be an actual table header line, not a mention in a comment.
        return (not _is_comment(line)) and line.startswith(header)

    def _uncomment_exact_header(line: str, header: str) -> str | None:
        stripped: str = line.lstrip()
        if stripped != f"# {header}":
            return None
        indent: str = line[: len(line) - len(stripped)]
        newline = "\n" if line.endswith("\n") else ""
        return f"{indent}{header}{newline}"

    def _find_section_end(start_idx: int) -> int:
        idx: int = start_idx + 1
        while idx < len(lines):
            stripped: str = lines[idx].lstrip()
            if stripped.startswith("[") and not stripped.startswith("#"):
                break
            idx += 1
        return idx

    def _find_commented_root_example(start_idx: int, end_idx: int) -> int | None:
        idx: int = start_idx + 1
        while idx < end_idx:
            if lines[idx].lstrip().strip() == "# root = true":
                return idx
            idx += 1
        return None

    def _is_root_line(line: str) -> bool:
        # Exact standalone `root = true`, not commented.
        return (not _is_comment(line)) and (line.strip() == _ROOT_LINE)

    target_header: str = _TOOL_TOPMARK_CONFIG_HEADER if for_pyproject else _CONFIG_HEADER

    target_header_idx: int | None = None
    for i, line in enumerate(lines):
        if _is_real_header(line, target_header):
            target_header_idx = i
            break

    if target_header_idx is None:
        for i, line in enumerate(lines):
            uncommented: str | None = _uncomment_exact_header(line, target_header)
            if uncommented is not None:
                lines[i] = uncommented
                target_header_idx = i
                break

    if root and target_header_idx is None:
        insert_at: int = 0
        if for_pyproject:
            tool_topmark_idx: int | None = None
            for i, line in enumerate(lines):
                if _is_real_header(line, _TOOL_TOPMARK_HEADER):
                    tool_topmark_idx = i
                    break
            if tool_topmark_idx is not None:
                insert_at = tool_topmark_idx + 1
                while insert_at < len(lines) and lines[insert_at].strip() == "":
                    insert_at += 1
        else:
            for i, line in enumerate(lines):
                if line.strip() == f"# {TOPMARK_END_MARKER}":
                    insert_at = i + 1
                    while insert_at < len(lines) and lines[insert_at].strip() == "":
                        insert_at += 1
                    break

        block: list[str] = [target_header + "\n", _ROOT_LINE + "\n"]
        if insert_at < len(lines) and lines[insert_at].strip() != "":
            block.append("\n")
        lines[insert_at:insert_at] = block
        return TemplateEditResult(text="".join(lines), changed=True)

    if target_header_idx is None:
        return TemplateEditResult(text=toml_text, changed=False)

    section_end: int = _find_section_end(target_header_idx)
    root_idxs: list[int] = [
        i for i in range(target_header_idx + 1, section_end) if _is_root_line(lines[i])
    ]

    if not root:
        if not root_idxs:
            return TemplateEditResult(text=toml_text, changed=False)

        new_lines: list[str] = []
        for i, line in enumerate(lines):
            if i in root_idxs:
                continue
            new_lines.append(line)
        return TemplateEditResult(text="".join(new_lines), changed=True)

    if root_idxs:
        if len(root_idxs) == 1:
            return TemplateEditResult(text=toml_text, changed=False)

        keep_idx = root_idxs[0]
        new_lines = []
        for i, line in enumerate(lines):
            if i in root_idxs and i != keep_idx:
                continue
            new_lines.append(line)
        return TemplateEditResult(text="".join(new_lines), changed=True)

    section_end = _find_section_end(target_header_idx)
    example_idx: int | None = _find_commented_root_example(target_header_idx, section_end)

    if example_idx is not None:
        insert_at = example_idx + 1
        # Do not skip blank lines.
    else:
        insert_at = target_header_idx + 1
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1

    lines.insert(insert_at, _ROOT_LINE + "\n")
    # Ensure a blank line after, unless we already have one.
    if insert_at + 1 < len(lines) and lines[insert_at + 1].strip() != "":
        lines.insert(insert_at + 1, "\n")

    return TemplateEditResult(text="".join(lines), changed=True)


def validate_toml_for_config_init(
    toml_text: str,
    *,
    for_pyproject: bool,
    root_expected: bool,
) -> None:
    """Validate final TOML output prepared for `topmark config init`.

    This is a defensive backstop for presentation-oriented edits of the bundled
    example TopMark TOML resource.

    Validates:
        - TOML syntax parses.
        - Minimal expected structure for the selected output mode (plain vs pyproject).
        - Optional `root` expectation (`[config].root` or `[tool.topmark.config].root`).

    Args:
        toml_text: Final TOML document text to validate.
        for_pyproject: If True, the document is expected to contain a `[tool]` table
            with a nested `[tool.topmark]` table.
        root_expected: If True, the document is expected to contain `root = true` in
            the appropriate scope (`[config].root` for non-pyproject output, or
            `[tool.topmark.config].root` for pyproject output).

    Raises:
        TemplateValidationError: If the generated TOML does not match the expected plain or
            pyproject shape, or if the produced text is not valid TOML.
    """
    try:
        doc: tomlkit.TOMLDocument = tomlkit.parse(toml_text)
    except TomlkitParseError as exc:
        raise TemplateValidationError(
            message=f"Invalid TOML produced by template surgery: {exc}",
        ) from exc

    def _has_real_header(header: str) -> bool:
        # Only count actual table headers, not comment mentions.
        for line in toml_text.splitlines():
            s: str = line.lstrip()
            if not s or s.startswith("#"):
                continue
            if s.startswith(header):
                return True
        return False

    if for_pyproject:
        # We expect actual tool/topmark tables in the parsed document.
        if "tool" not in doc:
            raise TemplateValidationError(
                message="Expected pyproject-style output but no [tool] table exists. "
                "This usually means [tool.topmark] was not inserted/nested.\n"
                f"Header scan: has [tool.topmark]={_has_real_header('[tool.topmark]')}, "
                f"has [tool.topmark.header]={_has_real_header('[tool.topmark.header]')}",
            )

        tool_item: Item = cast("Item", doc["tool"])
        if not isinstance(tool_item, Table):
            raise TemplateValidationError(
                message="Expected [tool] to be a TOML table, but it exists and is not a table.",
            )

        if "topmark" not in tool_item:
            raise TemplateValidationError(
                message="Expected [tool.topmark] table for pyproject-style output "
                "but it is missing.\n"
                "Note: comment mentions of '[tool.topmark]' do not create a table.\n"
                f"Header scan: has [tool.topmark]={_has_real_header('[tool.topmark]')}, "
                f"has [tool.topmark.header]={_has_real_header('[tool.topmark.header]')}",
            )

        topmark_item: Item = tool_item["topmark"]
        if not isinstance(topmark_item, Table):
            raise TemplateValidationError(
                message="Expected [tool.topmark] to be a TOML table, "
                " but it exists and is not a table.",
            )

        if root_expected:
            if "config" not in topmark_item:
                raise TemplateValidationError(
                    message="Expected `tool.topmark.config.root = true` "
                    "but `[tool.topmark.config]` is missing.",
                )
            config_item: Item = topmark_item["config"]
            if not isinstance(config_item, Table):
                raise TemplateValidationError(
                    message="Expected [tool.topmark.config] to be a TOML table, "
                    "but it exists and is not a table.",
                )
            if "root" not in config_item:
                raise TemplateValidationError(
                    message="Expected `tool.topmark.config.root = true` but `root` key is missing.",
                )
            root_val = config_item["root"]
            if getattr(root_val, "value", root_val) is not True:
                raise TemplateValidationError(
                    message="Expected `tool.topmark.config.root = true` but it is not true."
                )

    else:
        # Non-pyproject mode: root lives in [config] table.
        if root_expected:
            if "config" not in doc:
                raise TemplateValidationError(
                    message="Expected `[config].root = true` but `[config]` table is missing.",
                )
            config_item_raw: Item | Container = doc["config"]
            if not isinstance(config_item_raw, Table):
                raise TemplateValidationError(
                    message="Expected [config] to be a TOML table, "
                    "but it exists and is not a table.",
                )
            config_item = config_item_raw
            if "root" not in config_item:
                raise TemplateValidationError(
                    message="Expected `[config].root = true` but `root` key is missing.",
                )
            root_val: Item = config_item["root"]
            if getattr(root_val, "value", root_val) is not True:
                raise TemplateValidationError(
                    message="Expected `[config].root = true` but it is not true.",
                )
